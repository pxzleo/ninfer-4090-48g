#include "ninfer/engine.h"

#include "core/device.h"
#include "runtime/contract/sampling.h"
#include "runtime/contract/types.h"
#include "runtime/engine/concurrent_executor.h"
#include "targets/registry.h"

#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <deque>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>
#include <variant>
#include <vector>

namespace ninfer {
namespace {

runtime::ResolvedRequestOptions resolve_request_options(const ModelSamplingDefaults& defaults,
                                                        SamplingMode mode, RequestOptions options) {
    runtime::ResolvedRequestOptions resolved;
    resolved.execution.sampling =
        runtime::resolve_sampling(defaults, mode, options.execution.sampling);
    resolved.execution.requested_output_tokens = options.execution.requested_output_tokens;
    resolved.execution.allow_prefix_reuse      = options.execution.allow_prefix_reuse;
    resolved.stop                              = std::move(options.stop);
    resolved.output                            = options.output;
    return resolved;
}

} // namespace

class PreparedPrompt::Impl {
public:
    Impl(PromptSummary prompt_summary, double frontend_seconds, SamplingMode mode,
         targets::qwen3_6::PreparedPrompt prepared)
        : summary(std::move(prompt_summary)), prepare_seconds(frontend_seconds),
          sampling_mode(mode), value(std::move(prepared)) {}

    PromptSummary summary;
    double prepare_seconds     = 0.0;
    SamplingMode sampling_mode = SamplingMode::Thinking;
    targets::qwen3_6::PreparedPrompt value;
};

PreparedPrompt::PreparedPrompt() noexcept                            = default;
PreparedPrompt::~PreparedPrompt()                                    = default;
PreparedPrompt::PreparedPrompt(PreparedPrompt&&) noexcept            = default;
PreparedPrompt& PreparedPrompt::operator=(PreparedPrompt&&) noexcept = default;

PreparedPrompt::PreparedPrompt(std::unique_ptr<Impl> impl) noexcept : impl_(std::move(impl)) {}

const PromptSummary& PreparedPrompt::summary() const noexcept {
    static const PromptSummary empty;
    return impl_ != nullptr ? impl_->summary : empty;
}

PreparedPrompt::operator bool() const noexcept { return impl_ != nullptr; }

class GenerationHandle::Impl {
public:
    class Concept {
    public:
        virtual ~Concept() = default;
        virtual GenerationResult wait(OutputSink* sink, const CancellationView& cancellation) = 0;
    };

    template <class Submission>
    class Model final : public Concept {
    public:
        Model(std::shared_ptr<void> keep_alive, Submission submission)
            : keep_alive_(std::move(keep_alive)), submission_(std::move(submission)) {}

        GenerationResult wait(OutputSink* sink, const CancellationView& cancellation) override {
            return submission_.wait(sink, cancellation);
        }

    private:
        std::shared_ptr<void> keep_alive_;
        Submission submission_;
    };

    template <class Submission>
    Impl(std::shared_ptr<void> keep_alive, Submission submission,
         ResolvedSamplingParameters sampling)
        : state_(std::make_unique<Model<Submission>>(std::move(keep_alive), std::move(submission))),
          sampling_(sampling) {}

    GenerationResult wait(OutputSink* sink, const CancellationView& cancellation) {
        return state_->wait(sink, cancellation);
    }

    [[nodiscard]] const ResolvedSamplingParameters& resolved_sampling() const noexcept {
        return sampling_;
    }

private:
    std::unique_ptr<Concept> state_;
    ResolvedSamplingParameters sampling_;
};

GenerationHandle::GenerationHandle() noexcept                              = default;
GenerationHandle::~GenerationHandle()                                      = default;
GenerationHandle::GenerationHandle(GenerationHandle&&) noexcept            = default;
GenerationHandle& GenerationHandle::operator=(GenerationHandle&&) noexcept = default;

GenerationHandle::GenerationHandle(std::unique_ptr<Impl> impl) noexcept : impl_(std::move(impl)) {}

GenerationHandle::operator bool() const noexcept { return impl_ != nullptr; }

const ResolvedSamplingParameters& GenerationHandle::resolved_sampling() const noexcept {
    static const ResolvedSamplingParameters empty;
    return impl_ != nullptr ? impl_->resolved_sampling() : empty;
}

GenerationResult GenerationHandle::wait(OutputSink* sink, const CancellationView& cancellation) {
    if (impl_ == nullptr) { throw std::logic_error("GenerationHandle is empty"); }
    std::unique_ptr<Impl> impl = std::move(impl_);
    return impl->wait(sink, cancellation);
}

namespace {

std::string slot_model_binding(const LoadSummary& load) {
    return load.target + '\n' + load.model_id + '\n' + load.weights_id;
}

} // namespace

class Engine::Impl {
public:
    using Executor27 = runtime::ConcurrentExecutor<targets::Qwen3_6_27BInstance>;
    using Executor35 = runtime::ConcurrentExecutor<targets::Qwen3_6_35BA3BInstance>;
    using Executor =
        std::variant<std::monostate, std::unique_ptr<Executor27>, std::unique_ptr<Executor35>>;

    explicit Impl(EngineOptions engine_options)
        : options(std::move(engine_options)), device(options.device) {
        auto constructed  = targets::construct_target(options, device);
        active            = std::move(constructed.active);
        load              = std::move(constructed.load);
        sampling_defaults = constructed.sampling_defaults;
        executor          = std::visit(
            [&](auto& target_ptr) -> Executor {
                using Instance =
                    typename std::remove_reference_t<decltype(target_ptr)>::element_type;
                if constexpr (std::is_same_v<Instance, targets::Qwen3_6_27BInstance>) {
                    return std::make_unique<Executor27>(*target_ptr, options);
                } else {
                    return std::make_unique<Executor35>(*target_ptr, options);
                }
            },
            active);
        if (options.auto_save_evicted) {
            std::visit(
                [&](auto& constructed_executor) {
                    using ExecutorPtr = std::remove_cvref_t<decltype(constructed_executor)>;
                    if constexpr (!std::is_same_v<ExecutorPtr, std::monostate>) {
                        constructed_executor->set_eviction_sink(
                            slot_model_binding(load),
                            [this](std::string path,
                                   targets::qwen3_6::RetainedSessionSnapshot&& snapshot) {
                                enqueue_write(std::move(path), std::move(snapshot));
                            });
                    }
                },
                executor);
        }
    }

    ~Impl() noexcept {
        executor.emplace<std::monostate>();
        stop_writer();
        try {
            device.synchronize();
        } catch (...) {}
    }

    // Auto-save writer: eviction spills enqueue (path, snapshot) here; one background thread
    // publishes each file with the same write-then-rename discipline as an explicit save.
    struct PendingWrite {
        std::string path;
        targets::qwen3_6::RetainedSessionSnapshot snapshot;
    };

    void enqueue_write(std::string path, targets::qwen3_6::RetainedSessionSnapshot&& snapshot) {
        std::unique_lock lock(writer_mutex);
        if (!writer.joinable()) { writer = std::thread([this] { writer_loop(); }); }
        pending_writes.push_back(PendingWrite{std::move(path), std::move(snapshot)});
        lock.unlock();
        writer_cv.notify_one();
    }

    // Blocks until every enqueued auto-save has been published. Explicit slot operations call
    // this before touching files so a pending write can never be read stale or interleave with
    // a client save of the same path.
    void drain_writes() {
        std::unique_lock lock(writer_mutex);
        writer_cv.wait(lock, [this] { return pending_writes.empty() && !write_in_flight; });
    }

    EngineOptions options;
    DeviceContext device;
    targets::ActiveTarget active;
    LoadSummary load;
    ModelSamplingDefaults sampling_defaults;
    Executor executor;

    std::mutex writer_mutex;
    std::condition_variable writer_cv;
    std::deque<PendingWrite> pending_writes;
    bool write_in_flight = false;
    bool writer_stop     = false;
    std::thread writer;

private:
    void writer_loop() {
        std::unique_lock lock(writer_mutex);
        while (true) {
            writer_cv.wait(lock, [this] { return writer_stop || !pending_writes.empty(); });
            if (pending_writes.empty()) { break; }
            PendingWrite item = std::move(pending_writes.front());
            pending_writes.pop_front();
            write_in_flight = true;
            lock.unlock();

            SlotAutoSaveEvent event;
            event.path         = item.path;
            event.tokens       = item.snapshot.tokens;
            event.bytes        = item.snapshot.bytes.size();
            const auto started = std::chrono::steady_clock::now();
            try {
                write_snapshot_file(item.path, item.snapshot.bytes);
            } catch (const std::exception& error) {
                event.error = error.what();
            } catch (...) {
                event.error = "unknown auto-save failure";
            }
            event.seconds =
                std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
            if (options.auto_save_listener) {
                try {
                    options.auto_save_listener(event);
                } catch (...) {}
            }

            lock.lock();
            write_in_flight = false;
            writer_cv.notify_all();
        }
    }

    void stop_writer() noexcept {
        {
            std::scoped_lock lock(writer_mutex);
            writer_stop = true;
        }
        writer_cv.notify_all();
        if (writer.joinable()) {
            try {
                writer.join();
            } catch (...) {}
        }
    }

public:
    static void write_snapshot_file(const std::string& path,
                                    const std::vector<std::uint8_t>& bytes);
};

Engine::Engine(EngineOptions options) : impl_(std::make_shared<Impl>(std::move(options))) {}

Engine::~Engine()                            = default;
Engine::Engine(Engine&&) noexcept            = default;
Engine& Engine::operator=(Engine&&) noexcept = default;

PreparedPrompt Engine::prepare(PromptInput input) const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    const SamplingMode sampling_mode =
        input.options.enable_thinking ? SamplingMode::Thinking : SamplingMode::NonThinking;
    return std::visit(
        [&](const auto& target_ptr) -> PreparedPrompt {
            if (target_ptr == nullptr) { throw std::logic_error("Engine target is not active"); }
            auto prepared      = target_ptr->loaded->frontend.prepare(std::move(input));
            PromptSummary info = prepared.summary();
            if (info.prompt_tokens > target_ptr->capacity) {
                throw RequestError(RequestErrorKind::ContextLengthExceeded,
                                   "prepared prompt exceeds Engine context capacity");
            }
            const double seconds = prepared.prepare_seconds();
            return PreparedPrompt(std::make_unique<PreparedPrompt::Impl>(
                info, seconds, sampling_mode, std::move(prepared)));
        },
        impl_->active);
}

PreparedPrompt Engine::prepare_tokens(std::vector<TokenId> token_ids,
                                      bool allow_prefix_identity) const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return std::visit(
        [&](const auto& target_ptr) -> PreparedPrompt {
            if (target_ptr == nullptr) { throw std::logic_error("Engine target is not active"); }
            auto prepared      = target_ptr->loaded->frontend.prepare_tokens(std::move(token_ids),
                                                                             allow_prefix_identity);
            PromptSummary info = prepared.summary();
            if (info.prompt_tokens > target_ptr->capacity) {
                throw RequestError(RequestErrorKind::ContextLengthExceeded,
                                   "prepared prompt exceeds Engine context capacity");
            }
            const double seconds = prepared.prepare_seconds();
            return PreparedPrompt(std::make_unique<PreparedPrompt::Impl>(
                info, seconds, SamplingMode::Thinking, std::move(prepared)));
        },
        impl_->active);
}

std::uint32_t Engine::count_tokens(PromptInput input) const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return std::visit(
        [&](const auto& target_ptr) {
            if (target_ptr == nullptr) { throw std::logic_error("Engine target is not active"); }
            return target_ptr->loaded->frontend.count_tokens(std::move(input));
        },
        impl_->active);
}

PromptCapabilities Engine::prompt_capabilities() const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return std::visit(
        [](const auto& target_ptr) {
            if (target_ptr == nullptr) { throw std::logic_error("Engine target is not active"); }
            return target_ptr->loaded->frontend.prompt_capabilities();
        },
        impl_->active);
}

ModelSamplingDefaults Engine::sampling_defaults() const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return impl_->sampling_defaults;
}

GenerationHandle Engine::submit(PreparedPrompt prompt, RequestOptions options,
                                std::chrono::steady_clock::time_point pending_deadline,
                                HostInputLease host_input) {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    if (prompt.impl_ == nullptr) { throw std::invalid_argument("PreparedPrompt is empty"); }

    struct HostInputGuard {
        PreparedPrompt* prompt;
        HostInputLease* lease;

        ~HostInputGuard() {
            if (static_cast<bool>(*lease)) {
                prompt->impl_.reset();
                lease->reset();
            }
        }
    } host_input_guard{&prompt, &host_input};

    runtime::ResolvedRequestOptions resolved_options = resolve_request_options(
        impl_->sampling_defaults, prompt.impl_->sampling_mode, std::move(options));
    const ResolvedSamplingParameters resolved_sampling = resolved_options.execution.sampling;

    const PromptSummary prompt_summary = prompt.impl_->summary;
    if (prompt_summary.prompt_tokens > impl_->options.max_context) {
        throw RequestError(RequestErrorKind::ContextLengthExceeded,
                           "prepared prompt exceeds Engine context capacity");
    }
    const double prepare_seconds = prompt.impl_->prepare_seconds;
    if (resolved_options.execution.requested_output_tokens == 0) {
        struct ImmediateSubmission {
            GenerationResult result;

            GenerationResult wait(OutputSink*, const CancellationView& cancellation) {
                if (cancellation.requested()) { result.finish_reason = FinishReason::Cancelled; }
                return std::move(result);
            }
        } immediate;

        immediate.result.prompt                  = prompt_summary;
        immediate.result.finish_reason           = FinishReason::OutputLimit;
        immediate.result.timings.prepare_seconds = prepare_seconds;
        immediate.result.timings.total_seconds   = prepare_seconds;
        prompt.impl_.reset();
        host_input.reset();
        return GenerationHandle(std::make_unique<GenerationHandle::Impl>(
            impl_, std::move(immediate), resolved_sampling));
    }

    return std::visit(
        [&](auto& executor) -> GenerationHandle {
            using Executor = std::remove_cvref_t<decltype(executor)>;
            if constexpr (std::is_same_v<Executor, std::monostate>) {
                throw std::logic_error("concurrent Engine executor is unavailable");
            } else {
                auto submission = executor->submit(std::move(prompt.impl_->value), prompt_summary,
                                                   prepare_seconds, std::move(resolved_options),
                                                   pending_deadline, std::move(host_input));
                return GenerationHandle(std::make_unique<GenerationHandle::Impl>(
                    impl_, std::move(submission), resolved_sampling));
            }
        },
        impl_->executor);
}

GenerationResult Engine::generate(PreparedPrompt prompt, RequestOptions options, OutputSink* sink,
                                  const CancellationView& cancellation) {
    return submit(std::move(prompt), std::move(options)).wait(sink, cancellation);
}

const EngineOptions& Engine::options() const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return impl_->options;
}

LoadSummary Engine::load_summary() const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return impl_->load;
}

MemorySummary Engine::memory_summary() const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return std::visit(
        [](const auto& executor) -> MemorySummary {
            using Executor = std::remove_cvref_t<decltype(executor)>;
            if constexpr (std::is_same_v<Executor, std::monostate>) {
                throw std::logic_error("concurrent Engine executor is unavailable");
            } else {
                return executor->memory_summary();
            }
        },
        impl_->executor);
}

RuntimeStats Engine::runtime_stats() const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return std::visit(
        [](const auto& executor) -> RuntimeStats {
            using Executor = std::remove_cvref_t<decltype(executor)>;
            if constexpr (std::is_same_v<Executor, std::monostate>) {
                throw std::logic_error("concurrent Engine executor is unavailable");
            } else {
                return executor->runtime_stats();
            }
        },
        impl_->executor);
}

// Write-then-rename keeps a torn write from ever shadowing a good snapshot at `path`. The
// staging name embeds the thread id so a concurrent auto-save of the same path never shares a
// temporary file.
void Engine::Impl::write_snapshot_file(const std::string& path,
                                       const std::vector<std::uint8_t>& bytes) {
    std::ostringstream staging_name;
    staging_name << path << ".tmp." << std::this_thread::get_id();
    const std::string staging = staging_name.str();
    {
        std::ofstream file(staging, std::ios::binary | std::ios::trunc);
        file.write(reinterpret_cast<const char*>(bytes.data()),
                   static_cast<std::streamsize>(bytes.size()));
        if (!file.good()) {
            file.close();
            (void)std::remove(staging.c_str());
            throw std::invalid_argument("failed to write session snapshot file");
        }
    }
    std::error_code rename_error;
    std::filesystem::rename(staging, path, rename_error);
    if (rename_error) {
        (void)std::remove(staging.c_str());
        throw std::invalid_argument("failed to publish session snapshot file: " +
                                    rename_error.message());
    }
}

SlotSaveResult Engine::save_slot(std::uint32_t lane, const std::string& path,
                                 const std::string& expected_digest) {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    const auto started = std::chrono::steady_clock::now();
    // A pending auto-save of the same path must not land after this explicit save.
    impl_->drain_writes();
    const std::string binding = slot_model_binding(impl_->load);
    targets::qwen3_6::RetainedSessionSnapshot snapshot = std::visit(
        [&](auto& executor) -> targets::qwen3_6::RetainedSessionSnapshot {
            using Executor = std::remove_cvref_t<decltype(executor)>;
            if constexpr (std::is_same_v<Executor, std::monostate>) {
                throw std::logic_error("concurrent Engine executor is unavailable");
            } else {
                return executor->save_retained_lane(lane, binding, expected_digest, path);
            }
        },
        impl_->executor);

    Impl::write_snapshot_file(path, snapshot.bytes);

    SlotSaveResult result;
    result.tokens         = snapshot.tokens;
    result.bytes          = snapshot.bytes.size();
    result.session_digest = std::move(snapshot.session_digest);
    result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    return result;
}

SlotRestoreResult Engine::restore_slot(std::uint32_t lane, const std::string& path) {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    const auto started = std::chrono::steady_clock::now();
    // A restore must read the newest state, including a spill still in the writer queue.
    impl_->drain_writes();

    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file.is_open()) {
        throw std::invalid_argument("session snapshot file is unavailable");
    }
    const std::streamsize size = file.tellg();
    if (size <= 0) { throw std::invalid_argument("session snapshot file is empty"); }
    std::vector<std::uint8_t> snapshot(static_cast<std::size_t>(size));
    file.seekg(0);
    file.read(reinterpret_cast<char*>(snapshot.data()), size);
    if (!file.good()) { throw std::invalid_argument("failed to read session snapshot file"); }
    file.close();

    const std::string binding = slot_model_binding(impl_->load);
    auto restored = std::visit(
        [&](auto& executor) -> std::pair<std::uint32_t, std::string> {
            using Executor = std::remove_cvref_t<decltype(executor)>;
            if constexpr (std::is_same_v<Executor, std::monostate>) {
                throw std::logic_error("concurrent Engine executor is unavailable");
            } else {
                return executor->restore_retained_lane(
                    lane, std::span<const std::uint8_t>(snapshot.data(), snapshot.size()),
                    binding, path);
            }
        },
        impl_->executor);

    SlotRestoreResult result;
    result.tokens         = restored.first;
    result.bytes          = snapshot.size();
    result.session_digest = std::move(restored.second);
    result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    return result;
}

std::uint32_t Engine::erase_slot(std::uint32_t lane, const std::string& expected_digest) {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return std::visit(
        [&](auto& executor) -> std::uint32_t {
            using Executor = std::remove_cvref_t<decltype(executor)>;
            if constexpr (std::is_same_v<Executor, std::monostate>) {
                throw std::logic_error("concurrent Engine executor is unavailable");
            } else {
                return executor->erase_retained_lane(lane, expected_digest);
            }
        },
        impl_->executor);
}

std::vector<SlotState> Engine::slot_states() const {
    if (impl_ == nullptr) { throw std::logic_error("Engine is moved from"); }
    return std::visit(
        [](const auto& executor) -> std::vector<SlotState> {
            using Executor = std::remove_cvref_t<decltype(executor)>;
            if constexpr (std::is_same_v<Executor, std::monostate>) {
                throw std::logic_error("concurrent Engine executor is unavailable");
            } else {
                return executor->slot_states();
            }
        },
        impl_->executor);
}

void Engine::reset_memory_peaks() noexcept {
    if (impl_ == nullptr) { return; }
    std::visit(
        [](auto& executor) {
            using Executor = std::remove_cvref_t<decltype(executor)>;
            if constexpr (!std::is_same_v<Executor, std::monostate>) {
                executor->reset_memory_peaks();
            }
        },
        impl_->executor);
}

} // namespace ninfer
