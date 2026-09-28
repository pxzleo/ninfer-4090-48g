#include "runtime/engine/concurrent_executor.h"
#include "targets/qwen3_6/impl/frontend/test_access.h"

#include <nlohmann/json.hpp>

#include <condition_variable>
#include <fstream>
#include <iostream>
#include <iterator>
#include <mutex>
#include <stdexcept>

namespace {

using namespace ninfer;
using namespace ninfer::runtime;
namespace family = ninfer::targets::qwen3_6;

void require(bool value, const char* message) {
    if (!value) { throw std::runtime_error(message); }
}

family::Frontend frontend() {
    std::ifstream input(NINFER_SOURCE_DIR
                        "/tests/fixtures/frontend/thinking_toggle_chat_template.jinja");
    require(static_cast<bool>(input), "cannot read frontend template fixture");
    family::FrontendResources resources;
    resources.chat_template_jinja =
        std::string(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
    if (resources.chat_template_jinja.back() == '\n') {
        resources.chat_template_jinja.pop_back();
    }
    resources.tokenizer_json =
        R"({"model":{"type":"BPE","vocab":{"a":0,"b":1,"c":2,"x":3},"merges":[]},"added_tokens":[]})";
    resources.tokenizer_config_json =
        nlohmann::json{{"add_bos_token", false}, {"add_prefix_space", false},
                       {"pad_token", "<|endoftext|>"},
                       {"chat_template", resources.chat_template_jinja},
                       {"added_tokens_decoder", nlohmann::json::object()}}.dump();
    resources.generation_config_json = R"({"eos_token_id":[2]})";
    resources.preprocessor_config_json =
        R"({"patch_size":16,"temporal_patch_size":2,"merge_size":2,"image_mean":[0.5,0.5,0.5],"image_std":[0.5,0.5,0.5],"size":{"shortest_edge":4096,"longest_edge":16777216}})";
    resources.video_preprocessor_config_json = resources.preprocessor_config_json;
    return family::FrontendTestAccess::create_component(resources, false);
}

// Gate every execution unit. The test chooses when the unit may return, while the real
// executor chooses which request runs next. A timeout diagnoses deadlock, never determines
// scheduling order.
struct ExecutionGate {
    struct Event {
        TokenId request;
        bool decode;
    };
    std::mutex mutex;
    std::condition_variable cv;
    std::vector<Event> events;
    std::size_t permits = 0;
    bool unrestricted = false;

    void enter(TokenId request, bool decode = false) {
        std::unique_lock lock(mutex);
        events.push_back({request, decode});
        cv.notify_all();
        cv.wait(lock, [&] { return unrestricted || permits != 0; });
        if (!unrestricted) { --permits; }
    }

    Event wait(std::size_t count) {
        std::unique_lock lock(mutex);
        require(cv.wait_for(lock, std::chrono::seconds(5),
                            [&] { return events.size() >= count; }),
                "executor did not reach the next execution boundary");
        return events[count - 1];
    }

    void release() {
        std::lock_guard lock(mutex);
        ++permits;
        cv.notify_all();
    }

    void open() {
        std::lock_guard lock(mutex);
        unrestricted = true;
        cv.notify_all();
    }
};

struct FakeMemory {
    std::array<std::array<std::byte, 16>, kMaximumConcurrency> bytes{};
    std::array<bool, kMaximumConcurrency> active{};
    bool available = true;
    bool can_activate(std::uint32_t lane, std::size_t size, std::size_t alignment) const {
        return available && !active.at(lane) && size <= 16 && alignment == 1;
    }
    void activate(std::uint32_t lane, std::size_t size, std::size_t alignment) {
        require(can_activate(lane, size, alignment), "transient region activated twice");
        active[lane] = true;
    }
    void deactivate(std::uint32_t lane) { active.at(lane) = false; }
    TransientRegion region(std::uint32_t lane) {
        require(active.at(lane), "transient region is inactive");
        return {bytes[lane].data(), 16, 1};
    }
    ArenaMemorySummary summary() const {
        return {.capacity_bytes = bytes.size() * 16,
                .used_bytes = static_cast<std::size_t>(
                    std::count(active.begin(), active.end(), true)) * 16};
    }
};

struct FakePlan {
    RequestPlanSummary value;
    const RequestPlanSummary& summary() const { return value; }
};

struct FakeProgram {
    struct Lane {
        TokenId request = -1;
        std::uint32_t prompt = 0;
        std::uint32_t processed = 0;
        std::uint32_t reused = 0;
        bool retained = false;
        std::byte* transient = nullptr;
    };
    ExecutionGate gate;
    FakeMemory& memory;
    std::uint32_t concurrency;
    std::array<Lane, kMaximumConcurrency> lanes{};
    std::array<bool, 3> aborted{};
    std::array<bool, 3> finished{};
    std::array<TokenId, kMaximumConcurrency> output{};
    bool oversized_continuation = false;
    std::optional<std::uint32_t> failing_continuation_lane;

    explicit FakeProgram(FakeMemory& region_memory, std::uint32_t lane_count)
        : memory(region_memory), concurrency(lane_count) {
        output.fill(3);
    }
    AdmissionResources admission_capacity() const { return {concurrency, 64, 0}; }
    KvCacheUsage main_kv_cache_usage() const { return {}; }
    std::uint32_t main_kv_cache_tokens_lane(std::uint32_t lane) const {
        return lanes[lane].processed;
    }
    bool has_retained_lane(std::uint32_t lane) const { return lanes[lane].retained; }
    std::uint32_t retained_lane_depth(std::uint32_t lane) const {
        return lanes[lane].retained ? lanes[lane].processed : 0;
    }
    std::string retained_lane_digest(std::uint32_t lane) const {
        return lanes[lane].retained ? "retained" : "";
    }
    std::vector<SlotCheckpoint> retained_lane_checkpoints(std::uint32_t) const { return {}; }
    family::RetainedSessionSnapshot save_retained_lane(std::uint32_t, std::string_view) {
        return {};
    }
    GenerationTimings generation_timings_lane(std::uint32_t) const { return {}; }
    SpeculativeStats speculative_stats_lane(std::uint32_t) const { return {}; }
    void evict_retained_lane(std::uint32_t lane) { lanes[lane] = {}; }

    FakePlan plan_request_base(const family::PreparedPrompt& prompt,
                               const ResolvedExecutionOptions& options) {
        const auto count = prompt.summary().prompt_tokens;
        const auto marker = family::FrontendTestAccess::inspect(prompt).token_ids.front();
        return {{.prompt_tokens = count,
                 .requested_output_tokens = options.requested_output_tokens,
                 .effective_output_tokens = options.requested_output_tokens,
                 .effective_limit_reason = FinishReason::OutputLimit,
                 .transient_bytes = 16,
                 .transient_alignment = 1,
                 .admission = {1, marker == 2 && oversized_continuation ? 65U : 1U, 0},
                 .service_work_quanta = (count + 1) / 2 + options.requested_output_tokens}};
    }
    FakePlan plan_request_for_lane(std::uint32_t lane, const family::PreparedPrompt& prompt,
                                   const FakePlan& base) {
        FakePlan plan = base;
        const auto marker = family::FrontendTestAccess::inspect(prompt).token_ids.front();
        if (marker == 2 && failing_continuation_lane == lane) {
            throw std::runtime_error("test continuation lane plan failed");
        }
        if (lanes[lane].retained && lanes[lane].request == marker) {
            plan.value.reusable_prompt_tokens = std::min(lanes[lane].processed,
                                                         plan.value.prompt_tokens);
        }
        const auto remaining = plan.value.prompt_tokens - plan.value.reusable_prompt_tokens;
        plan.value.service_work_quanta = std::max(1U, (remaining + 1) / 2) +
                                         plan.value.effective_output_tokens;
        return plan;
    }
    bool can_admit_lane(std::uint32_t, const FakePlan&) const { return true; }
    bool can_admit_lane_with_retained_eviction(std::uint32_t, const FakePlan&,
                                               std::span<const std::uint32_t>) const {
        return true;
    }

    PrefillStepResult start_prefill_lane(std::uint32_t lane, family::PreparedPrompt prompt,
                                         FakePlan plan, TransientRegion transient,
                                         std::uint32_t chunk) {
        const auto marker = family::FrontendTestAccess::inspect(prompt).token_ids.front();
        lanes[lane] = {.request = marker,
                       .prompt = plan.value.prompt_tokens,
                       .processed = plan.value.reusable_prompt_tokens,
                       .reused = plan.value.reusable_prompt_tokens,
                       .transient = transient.data};
        return advance_prefill_lane(lane, chunk);
    }
    PrefillStepResult advance_prefill_lane(std::uint32_t lane, std::uint32_t chunk) {
        auto& state = lanes[lane];
        require(state.transient != nullptr && memory.active[lane] &&
                    memory.region(lane).data == state.transient,
                "prefill lost its lane's stable transient region");
        gate.enter(state.request);
        const auto processed = std::min(chunk, state.prompt - state.processed);
        state.processed += processed;
        const bool complete = state.processed == state.prompt;
        return {.summary = {.prompt_tokens = state.prompt,
                            .reused_prompt_tokens = state.reused,
                            .prefix_reuse_path = state.reused == 0
                                ? PrefixReusePath::FullReset : PrefixReusePath::AppendAtFrontier},
                .round = {complete ? std::span<const TokenId>(output.data(), 1)
                                   : std::span<const TokenId>()},
                .processed_prompt_tokens = processed,
                .complete = complete,
                .host_input_consumed = true};
    }
    void resolve_prefill_lane(std::uint32_t lane, bool terminal) {
        if (terminal) { finish(lane); }
    }
    BatchedGeneratedRound decode_batch(std::span<const std::uint32_t> selected,
                                       std::span<const RoundBudget>) {
        gate.enter(lanes[selected.front()].request, true);
        return {std::span<const TokenId>(output.data(), selected.size()), {}, 1};
    }
    void resolve_pending_batch(std::span<const std::uint32_t> selected,
                               std::span<const std::uint32_t>,
                               std::span<const std::uint8_t> terminal,
                               std::span<const std::uint8_t> cancelled) {
        for (std::size_t row = 0; row < selected.size(); ++row) {
            if (cancelled[row]) { abort_lane(selected[row]); }
            else if (terminal[row]) { finish(selected[row]); }
        }
    }
    void finish(std::uint32_t lane) {
        lanes[lane].retained = true;
        finished.at(lanes[lane].request) = true;
    }
    void abort_lane(std::uint32_t lane) {
        aborted.at(lanes[lane].request) = true;
        lanes[lane].retained = false;
    }
};

struct FakePackage {
    using Program = FakeProgram;
    using RequestBasePlan = FakePlan;
    using RequestPlan = FakePlan;
};

struct FakeInstance {
    using Package = FakePackage;
    struct Loaded { family::Frontend frontend = ::frontend(); };
    FakeMemory request_memory;
    std::unique_ptr<Loaded> loaded = std::make_unique<Loaded>();
    std::unique_ptr<FakeProgram> program;
    KvCapacityResolution kv_capacity_resolution;
    explicit FakeInstance(std::uint32_t concurrency)
        : program(std::make_unique<FakeProgram>(request_memory, concurrency)) {}
};

EngineOptions engine_options(std::uint32_t concurrency) {
    EngineOptions options;
    options.max_concurrency = concurrency;
    options.prefill_chunk = 2;
    options.prefill_chunk_when_decoding = 2;
    return options;
}

struct Harness {
    FakeInstance instance;
    ConcurrentExecutor<FakeInstance> executor;
    explicit Harness(std::uint32_t concurrency = 2)
        : instance(concurrency), executor(instance, engine_options(concurrency)) {}
    ~Harness() { instance.program->gate.open(); }
    auto submit(TokenId marker, std::uint32_t tokens, std::uint32_t output_tokens = 2,
                ConcurrentExecutor<FakeInstance>::Clock::time_point deadline = {}) {
        auto prompt = instance.loaded->frontend.prepare_tokens(std::vector<TokenId>(tokens, marker));
        const auto summary = prompt.summary();
        ResolvedRequestOptions options;
        options.execution.requested_output_tokens = output_tokens;
        return executor.submit(std::move(prompt), summary, 0, options, deadline);
    }
};

void cached_request_finishes_during_long_prefill() {
    Harness test;
    // Seed the same logical prefix a prior completed request would retain.
    // This setup occurs before submission wakes the worker.
    test.instance.program->lanes[1] = {.request = 2, .prompt = 8,
                                       .processed = 8, .retained = true};
    auto long_request = test.submit(0, 32);
    require(test.instance.program->gate.wait(1).request == 0, "long request did not start");
    auto short_request = test.submit(2, 9);
    bool short_decode = false;
    std::size_t boundary = 1;
    for (; boundary < 10 && !short_decode; ) {
        test.instance.program->gate.release();
        const auto event = test.instance.program->gate.wait(++boundary);
        short_decode = event.request == 2 && event.decode;
    }
    require(short_decode, "cached continuation waited behind the entire long prefill");
    test.instance.program->gate.release();
    test.instance.program->gate.wait(++boundary);
    const auto result = short_request.wait(nullptr, {});
    require(result.finish_reason == FinishReason::OutputLimit && result.content == "xx" &&
                result.reused_prompt_tokens == 8 && result.slot == 1,
            "cached continuation did not finish through the real output session");
    require(!test.instance.program->finished[0],
            "long request finished before the cached continuation");
    test.instance.program->gate.open();
    require(long_request.wait(nullptr, {}).generated_token_ids.size() == 2,
            "long request failed after the continuation");
}

void prefills_make_progress_and_cancel_independently() {
    Harness test;
    test.instance.program->lanes[0] = {.request = 0, .prompt = 8,
                                       .processed = 8, .retained = true};
    auto first = test.submit(0, 32);
    test.instance.program->gate.wait(1);
    require(test.executor.slot_states()[0].cached_tokens == 8,
            "partially prefilling slot lost its admitted cached-prefix count");
    auto second = test.submit(1, 32);
    std::array<unsigned, 2> progress{1, 0};
    std::size_t boundary = 1;
    bool multiple_prefills = false;
    for (; boundary < 10 && (progress[0] < 3 || progress[1] < 3); ) {
        test.instance.program->gate.release();
        const auto event = test.instance.program->gate.wait(++boundary);
        require(!event.decode, "a long prefill finished before its peer could progress");
        ++progress.at(event.request);
        const auto stats = test.executor.runtime_stats();
        multiple_prefills = multiple_prefills || stats.prefilling_requests == 2;
    }
    require(progress[0] >= 3 && progress[1] >= 3,
            "concurrent prefills did not both receive execution units");
    require(multiple_prefills, "runtime statistics never reported two active prefills");
    // Dropping a live submission uses the real consumer cancellation path.
    first = {};
    test.instance.program->gate.open();
    const auto result = second.wait(nullptr, {});
    require(result.finish_reason == FinishReason::OutputLimit && result.content == "xx",
            "cancelling one prefill damaged its peer");
    require(test.instance.program->aborted[0] && !test.instance.program->finished[0] &&
                test.instance.program->finished[1],
            "cancelled prefill was not aborted independently");
    require(!test.instance.request_memory.active[0] && !test.instance.request_memory.active[1],
            "completed or cancelled prefill retained its transient region");
    require(test.executor.runtime_stats().computed_prefill_tokens >= 32,
            "surviving prefill did not evaluate its whole prompt");
}

void queued_continuation_keeps_its_cached_lane() {
    Harness test(3);
    test.instance.program->lanes[0] = {.request = 2, .prompt = 8,
                                       .processed = 8, .retained = true};
    test.instance.program->lanes[1] = {.request = 1, .prompt = 16,
                                       .processed = 16, .retained = true};
    test.instance.program->lanes[2] = {.request = 1, .prompt = 32,
                                       .processed = 32, .retained = true};
    auto blocker = test.submit(1, 34);
    test.instance.program->gate.wait(1);
    auto cold_head = test.submit(0, 4);
    auto continuation = test.submit(2, 32);
    test.instance.program->gate.open();
    const auto cold_result = cold_head.wait(nullptr, {});
    const auto cached_result = continuation.wait(nullptr, {});
    require(cold_result.slot == 1 && cold_result.reused_prompt_tokens == 0 &&
                cold_result.content == "xx",
            "cold queue head replaced a prefix needed by the queued continuation");
    require(cached_result.slot == 0 && cached_result.reused_prompt_tokens == 8 &&
                cached_result.prefix_reuse_path == PrefixReusePath::AppendAtFrontier &&
                cached_result.content == "xx",
            "queued continuation lost its actual cached prefix");
    require(blocker.wait(nullptr, {}).reused_prompt_tokens == 32,
            "blocking request did not use the intended third lane");
}

void invalid_queued_continuation_does_not_protect_cache(bool oversized) {
    Harness test(3);
    test.instance.program->oversized_continuation = oversized;
    if (!oversized) { test.instance.program->failing_continuation_lane = 1; }
    test.instance.program->lanes[0] = {.request = 2, .prompt = 8,
                                       .processed = 8, .retained = true};
    test.instance.program->lanes[1] = {.request = 1, .prompt = 16,
                                       .processed = 16, .retained = true};
    test.instance.program->lanes[2] = {.request = 1, .prompt = 32,
                                       .processed = 32, .retained = true};
    auto blocker = test.submit(1, 34);
    test.instance.program->gate.wait(1);
    auto cold_head = test.submit(0, 4);
    auto invalid_continuation = test.submit(2, 32);
    test.instance.program->gate.open();
    const auto result = cold_head.wait(nullptr, {});
    require(result.slot == 0 && result.content == "xx",
            "invalid queued continuation protected a cache it cannot use");
    bool rejected = false;
    try {
        (void)invalid_continuation.wait(nullptr, {});
    } catch (const RequestError& error) {
        require(oversized && error.kind() == RequestErrorKind::ContextLengthExceeded,
                "oversized queued continuation returned an unrelated error");
        rejected = true;
    } catch (const std::runtime_error& error) {
        require(!oversized && std::string_view(error.what()) ==
                    "test continuation lane plan failed",
                "failed queued lane plan returned an unrelated error");
        rejected = true;
    }
    require(rejected, "invalid queued continuation was not rejected");
    require(blocker.wait(nullptr, {}).content == "xx",
            "invalid queued continuation damaged an admitted request");
}

void impossible_transient_is_rejected_without_execution() {
    Harness test;
    test.instance.request_memory.available = false;
    auto request = test.submit(0, 4, 2,
        ConcurrentExecutor<FakeInstance>::Clock::now() + std::chrono::seconds(5));
    bool rejected = false;
    try {
        (void)request.wait(nullptr, {});
    } catch (const std::logic_error& error) {
        require(std::string_view(error.what()) ==
                    "planned request transient exceeds the frozen Engine capacity",
                "impossible transient failed with an unrelated error");
        rejected = true;
    }
    require(rejected, "request with impossible transient was not rejected");
    require(test.instance.program->gate.events.empty(),
            "request executed without an available transient region");
}

} // namespace

int main() {
    try {
        cached_request_finishes_during_long_prefill();
        prefills_make_progress_and_cancel_independently();
        queued_continuation_keeps_its_cached_lane();
        invalid_queued_continuation_does_not_protect_cache(true);
        invalid_queued_continuation_does_not_protect_cache(false);
        impossible_transient_is_rejected_without_execution();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
