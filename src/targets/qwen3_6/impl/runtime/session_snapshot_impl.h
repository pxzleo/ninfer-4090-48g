#include "targets/qwen3_6/impl/runtime/instance.h"
#include "targets/qwen3_6/impl/runtime/program.h"

#include <cuda_runtime.h>

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

// Retained-session snapshot format (target-private, version 1).
//
// A snapshot is the complete host image of one idle retained lane: the resident prefix
// (ledger + identity), the paged Text/backend KV payload in logical page order, the lane's
// GDN linear-attention state, the MTP tail hidden, and the turn checkpoint when one is held.
// Byte order is the host's (x86 little-endian); a snapshot binds to the exact weights
// identity and KV configuration, so cross-endian portability is intentionally out of scope.
// Restore rebuilds a lane indistinguishable from one the engine retained itself: reuse
// planning sees AppendAtFrontier at the saved frontier or RestoreTurnCheckpoint at the saved
// checkpoint, and never anything the retained lane could not have offered.

namespace ninfer::targets::qwen3_6::detail::NINFER_QWEN36_RUNTIME_NS {
namespace {

constexpr char kSessionSnapshotMagic[8] = {'N', 'I', 'N', 'F', 'S', 'E', 'S', '1'};
constexpr std::uint32_t kSessionSnapshotVersion = 1;
// Version 2 appends the host turn-checkpoint ring after the KV payload. A snapshot with an
// empty ring is still written as version 1 so binaries without ring support keep reading it.
constexpr std::uint32_t kSessionSnapshotVersionRing = 2;
constexpr std::uint32_t kSessionSnapshotMaxRingEntries = 64;

constexpr std::uint32_t kKvFlagPackedV    = 1U << 0;
constexpr std::uint32_t kKvFlagRotateK    = 1U << 1;
constexpr std::uint32_t kKvFlagRotateV    = 1U << 2;
constexpr std::uint32_t kKvFlagPackedK    = 1U << 3;
constexpr std::uint32_t kKvFlagE8Lattice  = 1U << 4;
constexpr std::uint32_t kKvFlagE8Root     = 1U << 5;

class SnapshotWriter {
public:
    explicit SnapshotWriter(std::vector<std::uint8_t>& out) : out_(out) {}

    void bytes(const void* data, std::size_t count) {
        const auto* begin = static_cast<const std::uint8_t*>(data);
        out_.insert(out_.end(), begin, begin + count);
    }

    template <class T>
    void pod(T value) {
        static_assert(std::is_trivially_copyable_v<T>);
        bytes(&value, sizeof(T));
    }

    // Reserves a device-payload region and returns its offset; the caller fills it with
    // cudaMemcpyAsync once the full host image is sized (the vector no longer reallocates).
    std::size_t reserve_payload(std::size_t count) {
        const std::size_t offset = out_.size();
        out_.resize(out_.size() + count);
        return offset;
    }

private:
    std::vector<std::uint8_t>& out_;
};

class SnapshotReader {
public:
    explicit SnapshotReader(std::span<const std::uint8_t> data) : data_(data) {}

    void bytes(void* out, std::size_t count) {
        if (count > data_.size() - cursor_) {
            throw std::invalid_argument("session snapshot is truncated");
        }
        std::memcpy(out, data_.data() + cursor_, count);
        cursor_ += count;
    }

    template <class T>
    [[nodiscard]] T pod() {
        static_assert(std::is_trivially_copyable_v<T>);
        T value{};
        bytes(&value, sizeof(T));
        return value;
    }

    // Borrows a device-payload region without copying; valid for the snapshot's lifetime.
    [[nodiscard]] const std::uint8_t* payload(std::size_t count) {
        if (count > data_.size() - cursor_) {
            throw std::invalid_argument("session snapshot is truncated");
        }
        const std::uint8_t* region = data_.data() + cursor_;
        cursor_ += count;
        return region;
    }

    [[nodiscard]] std::size_t remaining() const noexcept { return data_.size() - cursor_; }

private:
    std::span<const std::uint8_t> data_;
    std::size_t cursor_ = 0;
};

template <class T>
void write_vector(SnapshotWriter& writer, const std::vector<T>& values) {
    static_assert(std::is_trivially_copyable_v<T>);
    writer.pod<std::uint64_t>(values.size());
    writer.bytes(values.data(), values.size() * sizeof(T));
}

template <class T>
std::vector<T> read_vector(SnapshotReader& reader, std::size_t maximum_count, const char* label) {
    const std::uint64_t count = reader.pod<std::uint64_t>();
    if (count > maximum_count) {
        throw std::invalid_argument(std::string("session snapshot ") + label +
                                    " count is out of range");
    }
    std::vector<T> values(static_cast<std::size_t>(count));
    reader.bytes(values.data(), values.size() * sizeof(T));
    return values;
}

void write_vision_items(SnapshotWriter& writer, const std::vector<VisionItem>& items) {
    writer.pod<std::uint32_t>(static_cast<std::uint32_t>(items.size()));
    for (const VisionItem& item : items) {
        writer.pod<std::uint8_t>(static_cast<std::uint8_t>(item.modality));
        writer.pod<std::int32_t>(item.grid.temporal);
        writer.pod<std::int32_t>(item.grid.height);
        writer.pod<std::int32_t>(item.grid.width);
        writer.pod<std::uint64_t>(item.patch_begin);
        writer.pod<std::uint64_t>(item.patch_count);
        writer.bytes(item.content_digest.data(), item.content_digest.size());
        write_vector(writer, item.timestamps);
        writer.pod<std::uint32_t>(static_cast<std::uint32_t>(item.token_spans.size()));
        for (const TokenSpan& span : item.token_spans) {
            writer.pod<std::uint64_t>(span.begin);
            writer.pod<std::uint64_t>(span.count);
        }
    }
}

std::vector<VisionItem> read_vision_items(SnapshotReader& reader, std::size_t tokens) {
    const std::uint32_t count = reader.pod<std::uint32_t>();
    if (count > tokens) {
        throw std::invalid_argument("session snapshot vision item count is out of range");
    }
    std::vector<VisionItem> items(count);
    for (VisionItem& item : items) {
        item.modality      = static_cast<PromptModality>(reader.pod<std::uint8_t>());
        item.grid.temporal = reader.pod<std::int32_t>();
        item.grid.height   = reader.pod<std::int32_t>();
        item.grid.width    = reader.pod<std::int32_t>();
        item.patch_begin   = static_cast<std::size_t>(reader.pod<std::uint64_t>());
        item.patch_count   = static_cast<std::size_t>(reader.pod<std::uint64_t>());
        reader.bytes(item.content_digest.data(), item.content_digest.size());
        item.timestamps = read_vector<double>(reader, tokens, "vision timestamp");
        const std::uint32_t spans = reader.pod<std::uint32_t>();
        if (spans > tokens) {
            throw std::invalid_argument("session snapshot vision span count is out of range");
        }
        item.token_spans.resize(spans);
        for (TokenSpan& span : item.token_spans) {
            span.begin = static_cast<std::size_t>(reader.pod<std::uint64_t>());
            span.count = static_cast<std::size_t>(reader.pod<std::uint64_t>());
        }
    }
    return items;
}

struct SnapshotConfig {
    std::uint32_t kv_dtype             = 0;
    std::int32_t kv_quant_group        = 0;
    std::uint32_t kv_flags             = 0;
    std::uint32_t speculative_backend  = 0;
    std::uint32_t draft_window         = 0;
    std::uint32_t page_size            = 0;
    std::uint32_t gdn_layers           = 0;
    std::uint64_t conv_slot_bytes      = 0;
    std::uint64_t recurrent_slot_bytes = 0;
    std::uint64_t tail_hidden_bytes    = 0;
    std::uint32_t text_plane_count     = 0;
    std::uint64_t text_page_bytes      = 0;
    std::uint32_t backend_plane_count  = 0;
    std::uint64_t backend_page_bytes   = 0;
};

struct SnapshotSession {
    std::uint32_t tokens                   = 0;
    std::uint32_t execution_frontier       = 0;
    std::uint32_t ledger_frontier          = 0;
    std::uint32_t text_kv_valid            = 0;
    std::uint32_t mtp_kv_valid             = 0;
    std::int32_t rope_delta                = 0;
    std::uint8_t tail_hidden_valid         = 0;
    std::uint8_t turn_checkpoint_valid     = 0;
    std::uint32_t turn_checkpoint_frontier = 0;
    std::uint32_t text_pages               = 0;
    std::uint32_t backend_pages            = 0;
};

void write_config(SnapshotWriter& writer, const SnapshotConfig& config) {
    writer.pod(config.kv_dtype);
    writer.pod(config.kv_quant_group);
    writer.pod(config.kv_flags);
    writer.pod(config.speculative_backend);
    writer.pod(config.draft_window);
    writer.pod(config.page_size);
    writer.pod(config.gdn_layers);
    writer.pod(config.conv_slot_bytes);
    writer.pod(config.recurrent_slot_bytes);
    writer.pod(config.tail_hidden_bytes);
    writer.pod(config.text_plane_count);
    writer.pod(config.text_page_bytes);
    writer.pod(config.backend_plane_count);
    writer.pod(config.backend_page_bytes);
}

SnapshotConfig read_config(SnapshotReader& reader) {
    SnapshotConfig config;
    config.kv_dtype             = reader.pod<std::uint32_t>();
    config.kv_quant_group       = reader.pod<std::int32_t>();
    config.kv_flags             = reader.pod<std::uint32_t>();
    config.speculative_backend  = reader.pod<std::uint32_t>();
    config.draft_window         = reader.pod<std::uint32_t>();
    config.page_size            = reader.pod<std::uint32_t>();
    config.gdn_layers           = reader.pod<std::uint32_t>();
    config.conv_slot_bytes      = reader.pod<std::uint64_t>();
    config.recurrent_slot_bytes = reader.pod<std::uint64_t>();
    config.tail_hidden_bytes    = reader.pod<std::uint64_t>();
    config.text_plane_count     = reader.pod<std::uint32_t>();
    config.text_page_bytes      = reader.pod<std::uint64_t>();
    config.backend_plane_count  = reader.pod<std::uint32_t>();
    config.backend_page_bytes   = reader.pod<std::uint64_t>();
    return config;
}

void write_session(SnapshotWriter& writer, const SnapshotSession& session) {
    writer.pod(session.tokens);
    writer.pod(session.execution_frontier);
    writer.pod(session.ledger_frontier);
    writer.pod(session.text_kv_valid);
    writer.pod(session.mtp_kv_valid);
    writer.pod(session.rope_delta);
    writer.pod(session.tail_hidden_valid);
    writer.pod(session.turn_checkpoint_valid);
    writer.pod(session.turn_checkpoint_frontier);
    writer.pod(session.text_pages);
    writer.pod(session.backend_pages);
}

SnapshotSession read_session(SnapshotReader& reader) {
    SnapshotSession session;
    session.tokens                   = reader.pod<std::uint32_t>();
    session.execution_frontier       = reader.pod<std::uint32_t>();
    session.ledger_frontier          = reader.pod<std::uint32_t>();
    session.text_kv_valid            = reader.pod<std::uint32_t>();
    session.mtp_kv_valid             = reader.pod<std::uint32_t>();
    session.rope_delta               = reader.pod<std::int32_t>();
    session.tail_hidden_valid        = reader.pod<std::uint8_t>();
    session.turn_checkpoint_valid    = reader.pod<std::uint8_t>();
    session.turn_checkpoint_frontier = reader.pod<std::uint32_t>();
    session.text_pages               = reader.pod<std::uint32_t>();
    session.backend_pages            = reader.pod<std::uint32_t>();
    return session;
}

// Session identity: FNV-1a 64 over the resident ledger's token bytes, rendered as 16 hex
// chars. Deterministic across processes on one endianness, which snapshot compatibility
// already requires. The shared prefix form lives in program_impl.h so ring checkpoints hash
// identically.
std::string ledger_digest(const std::vector<TokenId>& ledger) {
    return ledger_prefix_digest(std::span<const TokenId>(ledger.data(), ledger.size()));
}

} // namespace

std::uint32_t ProgramImplCore::retained_lane_depth(std::uint32_t lane) const noexcept {
    if (lane >= max_concurrency || !sequences[lane].retained) { return 0; }
    return static_cast<std::uint32_t>(sequences[lane].ledger.size());
}

std::string ProgramImplCore::retained_lane_digest(std::uint32_t lane) const {
    if (lane >= max_concurrency || !sequences[lane].retained) { return {}; }
    return ledger_digest(sequences[lane].ledger);
}

std::vector<SlotCheckpoint>
ProgramImplCore::retained_lane_checkpoints(std::uint32_t lane) const {
    if (lane >= max_concurrency || !sequences[lane].retained) { return {}; }
    const SequenceState& sequence = sequences[lane];
    std::vector<SlotCheckpoint> out;
    out.reserve(sequence.checkpoint_ring.size() + 1);
    for (const HostTurnCheckpoint& entry : sequence.checkpoint_ring) {
        out.push_back(SlotCheckpoint{entry.frontier, entry.session_digest});
    }
    // The staged (newest) checkpoint has not been folded into the ring yet; report it so the
    // listing matches what a diverging prompt could actually restore.
    const CheckpointStaging& staging = checkpoint_staging[lane];
    if (staging.pending && (out.empty() || out.back().frontier != staging.frontier)) {
        out.push_back(SlotCheckpoint{staging.frontier, staging.session_digest});
    }
    return out;
}

qwen3_6::RetainedSessionSnapshot
ProgramImplCore::save_retained_lane(std::uint32_t lane, std::string_view model_binding) {
    if (lane >= max_concurrency) { throw std::out_of_range("request lane is out of range"); }
    const RequestControl& request = requests[lane];
    SequenceState& sequence       = sequences[lane];
    if (request.lifecycle == Lifecycle::Prefilling || request.lifecycle == Lifecycle::Active ||
        request.lifecycle == Lifecycle::Pending) {
        throw std::logic_error("cannot snapshot a lane with an active request");
    }
    if (!sequence.retained || !sequence.kv) {
        throw std::invalid_argument("lane holds no retained session");
    }
    if (speculative_backend == SpeculativeBackend::DFlash) {
        throw std::invalid_argument("session persistence does not support the DFlash backend");
    }
    if (model_binding.size() > 4096) {
        throw std::invalid_argument("session snapshot model binding is too long");
    }

    const std::size_t tokens = sequence.ledger.size();
    if (tokens == 0 || tokens > capacity || sequence.prefix_identity.size() != tokens ||
        sequence.ledger_frontier != tokens || sequence.execution_frontier > tokens ||
        tokens - sequence.execution_frontier > 1) {
        throw std::logic_error("retained session ledger and identity are inconsistent");
    }

    // Fold any staged checkpoint into the ring first so the snapshot carries every restorable
    // frontier the lane holds.
    if (checkpoint_ring_capacity != 0) { drain_checkpoint_staging(sequence); }
    if (backend_kv_cache() != nullptr &&
        (!sequence.kv->backend || sequence.kv->backend->page_ids().empty())) {
        throw std::invalid_argument("retained session is too shallow to snapshot");
    }

    const PagedKVPool& text_pool = decoder->text_kv.pool();
    const qwen3_6::PagedKVCache* backend = backend_kv_cache();
    const std::span<const std::int32_t> text_pages = sequence.kv->text.page_ids();
    const std::span<const std::int32_t> backend_pages =
        backend != nullptr && sequence.kv->backend ? sequence.kv->backend->page_ids()
                                                   : std::span<const std::int32_t>{};

    const LinearAttentionStatePool& states = decoder->linear_attention;
    const std::int32_t current_slot    = LinearStateSlots::current_state_slot(lane, max_concurrency);
    const std::int32_t checkpoint_slot =
        LinearStateSlots::turn_checkpoint_state_slot(lane, max_concurrency);
    const std::size_t conv_bytes      = states.conv_slot(0, current_slot).bytes();
    const std::size_t recurrent_bytes = states.recurrent_slot(0, current_slot).bytes();

    SnapshotConfig config;
    config.kv_dtype            = static_cast<std::uint32_t>(kv_dtype);
    config.kv_quant_group      = kv_quant_group;
    config.kv_flags            = (kv_packed_v ? kKvFlagPackedV : 0U) |
                      (kv_rotate_k ? kKvFlagRotateK : 0U) | (kv_rotate_v ? kKvFlagRotateV : 0U) |
                      (kv_packed_k ? kKvFlagPackedK : 0U) |
                      (kv_e8_lattice ? kKvFlagE8Lattice : 0U) | (kv_e8_root ? kKvFlagE8Root : 0U);
    config.speculative_backend  = static_cast<std::uint32_t>(speculative_backend);
    config.draft_window         = draft_window;
    config.page_size            = static_cast<std::uint32_t>(kPagedKVPageSize);
    config.gdn_layers           = states.layer_count();
    config.conv_slot_bytes      = conv_bytes;
    config.recurrent_slot_bytes = recurrent_bytes;
    config.tail_hidden_bytes    = sequence.tail_hidden.bytes();
    config.text_plane_count     = static_cast<std::uint32_t>(text_pool.plane_count());
    config.text_page_bytes      = text_pool.page_payload_bytes();
    if (backend != nullptr) {
        config.backend_plane_count = static_cast<std::uint32_t>(backend->pool().plane_count());
        config.backend_page_bytes  = backend->pool().page_payload_bytes();
    }

    SnapshotSession session;
    session.tokens                   = static_cast<std::uint32_t>(tokens);
    session.execution_frontier       = sequence.execution_frontier;
    session.ledger_frontier          = sequence.ledger_frontier;
    session.text_kv_valid            = sequence.text_kv_valid;
    session.mtp_kv_valid             = sequence.mtp_kv_valid;
    session.rope_delta               = sequence.rope_delta;
    session.tail_hidden_valid        = sequence.tail_hidden_valid ? 1 : 0;
    session.turn_checkpoint_valid    = sequence.turn_checkpoint.valid ? 1 : 0;
    session.turn_checkpoint_frontier = sequence.turn_checkpoint.frontier;
    session.text_pages               = static_cast<std::uint32_t>(text_pages.size());
    session.backend_pages            = static_cast<std::uint32_t>(backend_pages.size());

    // A snapshot without ring entries stays version 1 so pre-ring binaries keep reading it.
    const std::size_t ring_skip =
        sequence.checkpoint_ring.size() > kSessionSnapshotMaxRingEntries
            ? sequence.checkpoint_ring.size() - kSessionSnapshotMaxRingEntries
            : 0;
    const std::span<const HostTurnCheckpoint> ring_entries(
        sequence.checkpoint_ring.data() + ring_skip, sequence.checkpoint_ring.size() - ring_skip);
    for (const HostTurnCheckpoint& entry : ring_entries) {
        if (entry.hidden.size() != config.tail_hidden_bytes ||
            entry.conv.size() != conv_bytes * config.gdn_layers ||
            entry.recurrent.size() != recurrent_bytes * config.gdn_layers) {
            throw std::logic_error("retained checkpoint ring geometry is inconsistent");
        }
    }

    qwen3_6::RetainedSessionSnapshot snapshot;
    snapshot.tokens         = session.tokens;
    snapshot.session_digest = ledger_digest(sequence.ledger);
    SnapshotWriter writer(snapshot.bytes);
    writer.bytes(kSessionSnapshotMagic, sizeof(kSessionSnapshotMagic));
    writer.pod(ring_entries.empty() ? kSessionSnapshotVersion : kSessionSnapshotVersionRing);
    writer.pod<std::uint32_t>(static_cast<std::uint32_t>(model_binding.size()));
    writer.bytes(model_binding.data(), model_binding.size());
    write_config(writer, config);
    write_session(writer, session);
    write_vector(writer, sequence.ledger);
    write_vector(writer, sequence.prefix_identity.token_types());
    for (std::size_t axis = 0; axis < 3; ++axis) {
        write_vector(writer, sequence.prefix_identity.position_axis(axis));
    }
    write_vision_items(writer, sequence.prefix_identity.vision_items());

    // Size the device payload in one pass so the vector's storage is final before any
    // cudaMemcpyAsync records a destination pointer.
    struct GdnRegion {
        std::size_t conv      = 0;
        std::size_t recurrent = 0;
    };
    const bool save_checkpoint = sequence.turn_checkpoint.valid;
    std::size_t tail_offset    = 0;
    if (sequence.tail_hidden_valid) {
        tail_offset = writer.reserve_payload(config.tail_hidden_bytes);
    }
    GdnRegion current_region;
    current_region.conv      = writer.reserve_payload(conv_bytes * config.gdn_layers);
    current_region.recurrent = writer.reserve_payload(recurrent_bytes * config.gdn_layers);
    std::size_t checkpoint_hidden_offset = 0;
    GdnRegion checkpoint_region;
    if (save_checkpoint) {
        checkpoint_hidden_offset  = writer.reserve_payload(config.tail_hidden_bytes);
        checkpoint_region.conv    = writer.reserve_payload(conv_bytes * config.gdn_layers);
        checkpoint_region.recurrent = writer.reserve_payload(recurrent_bytes * config.gdn_layers);
    }
    const std::size_t text_kv_offset =
        writer.reserve_payload(config.text_page_bytes * session.text_pages);
    const std::size_t backend_kv_offset =
        writer.reserve_payload(config.backend_page_bytes * session.backend_pages);

    // Ring entries are host data, so they are written inline during the sizing pass; they land
    // after the KV payload regions in the byte stream. Nothing may grow the vector once the
    // payload base pointer below is taken.
    if (!ring_entries.empty()) {
        writer.pod<std::uint32_t>(static_cast<std::uint32_t>(ring_entries.size()));
        for (const HostTurnCheckpoint& entry : ring_entries) {
            writer.pod<std::uint32_t>(entry.frontier);
            writer.bytes(entry.hidden.data(), entry.hidden.size());
            writer.bytes(entry.conv.data(), entry.conv.size());
            writer.bytes(entry.recurrent.data(), entry.recurrent.size());
        }
    }

    std::uint8_t* base = snapshot.bytes.data();
    const auto copy_gdn_slot = [&](std::int32_t slot, const GdnRegion& region) {
        for (std::uint32_t layer = 0; layer < config.gdn_layers; ++layer) {
            const Tensor conv = states.conv_slot(layer, slot);
            CUDA_CHECK(cudaMemcpyAsync(base + region.conv + layer * conv_bytes, conv.data,
                                       conv_bytes, cudaMemcpyDeviceToHost, device.stream));
            const Tensor recurrent = states.recurrent_slot(layer, slot);
            CUDA_CHECK(cudaMemcpyAsync(base + region.recurrent + layer * recurrent_bytes,
                                       recurrent.data, recurrent_bytes, cudaMemcpyDeviceToHost,
                                       device.stream));
        }
    };
    if (sequence.tail_hidden_valid) {
        CUDA_CHECK(cudaMemcpyAsync(base + tail_offset, sequence.tail_hidden.data,
                                   config.tail_hidden_bytes, cudaMemcpyDeviceToHost,
                                   device.stream));
    }
    copy_gdn_slot(current_slot, current_region);
    if (save_checkpoint) {
        CUDA_CHECK(cudaMemcpyAsync(base + checkpoint_hidden_offset,
                                   sequence.turn_checkpoint_hidden.data, config.tail_hidden_bytes,
                                   cudaMemcpyDeviceToHost, device.stream));
        copy_gdn_slot(checkpoint_slot, checkpoint_region);
    }
    text_pool.copy_pages_to_host(text_pages, base + text_kv_offset, device.stream);
    if (!backend_pages.empty()) {
        backend->pool().copy_pages_to_host(backend_pages, base + backend_kv_offset, device.stream);
    }
    device.synchronize();
    return snapshot;
}

std::uint32_t ProgramImplCore::restore_retained_lane(std::uint32_t lane,
                                                     std::span<const std::uint8_t> snapshot,
                                                     std::string_view model_binding) {
    if (lane >= max_concurrency) { throw std::out_of_range("request lane is out of range"); }
    RequestControl& request = requests[lane];
    SequenceState& sequence = sequences[lane];
    if (request.lifecycle == Lifecycle::Prefilling || request.lifecycle == Lifecycle::Active ||
        request.lifecycle == Lifecycle::Pending) {
        throw std::logic_error("cannot restore into a lane with an active request");
    }
    if (sequence.retained || sequence.kv) {
        throw std::logic_error("cannot restore into a lane holding a retained session");
    }
    if (speculative_backend == SpeculativeBackend::DFlash) {
        throw std::invalid_argument("session persistence does not support the DFlash backend");
    }

    SnapshotReader reader(snapshot);
    char magic[sizeof(kSessionSnapshotMagic)] = {};
    reader.bytes(magic, sizeof(magic));
    if (std::memcmp(magic, kSessionSnapshotMagic, sizeof(magic)) != 0) {
        throw std::invalid_argument("file is not a session snapshot");
    }
    const std::uint32_t version = reader.pod<std::uint32_t>();
    if (version != kSessionSnapshotVersion && version != kSessionSnapshotVersionRing) {
        throw std::invalid_argument("session snapshot version is unsupported");
    }
    const std::uint32_t binding_bytes = reader.pod<std::uint32_t>();
    if (binding_bytes > 4096) {
        throw std::invalid_argument("session snapshot model binding is too long");
    }
    std::string binding(binding_bytes, '\0');
    reader.bytes(binding.data(), binding_bytes);
    if (binding != model_binding) {
        throw std::invalid_argument("session snapshot was saved for a different model");
    }

    const PagedKVPool& text_pool         = decoder->text_kv.pool();
    const qwen3_6::PagedKVCache* backend = backend_kv_cache();
    const LinearAttentionStatePool& states = decoder->linear_attention;
    const std::int32_t current_slot    = LinearStateSlots::current_state_slot(lane, max_concurrency);
    const std::int32_t checkpoint_slot =
        LinearStateSlots::turn_checkpoint_state_slot(lane, max_concurrency);
    const std::size_t conv_bytes      = states.conv_slot(0, current_slot).bytes();
    const std::size_t recurrent_bytes = states.recurrent_slot(0, current_slot).bytes();

    const SnapshotConfig config = read_config(reader);
    const std::uint32_t expected_flags =
        (kv_packed_v ? kKvFlagPackedV : 0U) | (kv_rotate_k ? kKvFlagRotateK : 0U) |
        (kv_rotate_v ? kKvFlagRotateV : 0U) | (kv_packed_k ? kKvFlagPackedK : 0U) |
        (kv_e8_lattice ? kKvFlagE8Lattice : 0U) | (kv_e8_root ? kKvFlagE8Root : 0U);
    if (config.kv_dtype != static_cast<std::uint32_t>(kv_dtype) ||
        config.kv_quant_group != kv_quant_group || config.kv_flags != expected_flags ||
        config.page_size != static_cast<std::uint32_t>(kPagedKVPageSize) ||
        config.text_plane_count != static_cast<std::uint32_t>(text_pool.plane_count()) ||
        config.text_page_bytes != text_pool.page_payload_bytes()) {
        throw std::invalid_argument("session snapshot KV configuration does not match the server");
    }
    if (config.speculative_backend != static_cast<std::uint32_t>(speculative_backend) ||
        config.draft_window != draft_window) {
        throw std::invalid_argument(
            "session snapshot speculative configuration does not match the server");
    }
    const std::uint32_t backend_plane_count =
        backend != nullptr ? static_cast<std::uint32_t>(backend->pool().plane_count()) : 0U;
    const std::uint64_t backend_page_bytes =
        backend != nullptr ? backend->pool().page_payload_bytes() : 0U;
    if (config.backend_plane_count != backend_plane_count ||
        config.backend_page_bytes != backend_page_bytes) {
        throw std::invalid_argument(
            "session snapshot backend KV configuration does not match the server");
    }
    if (config.gdn_layers != states.layer_count() || config.conv_slot_bytes != conv_bytes ||
        config.recurrent_slot_bytes != recurrent_bytes ||
        config.tail_hidden_bytes != sequence.tail_hidden.bytes()) {
        throw std::invalid_argument("session snapshot state geometry does not match the server");
    }

    const SnapshotSession session = read_session(reader);
    if (session.tokens == 0 || session.tokens > capacity) {
        throw std::invalid_argument("session snapshot depth exceeds the server context");
    }
    if (session.ledger_frontier != session.tokens ||
        session.execution_frontier > session.tokens ||
        session.tokens - session.execution_frontier > 1 ||
        session.text_kv_valid > session.execution_frontier ||
        session.mtp_kv_valid > session.tokens ||
        session.turn_checkpoint_frontier > session.tokens) {
        throw std::invalid_argument("session snapshot frontiers are inconsistent");
    }
    const auto covers = [](std::uint32_t pages, std::uint32_t tokens_needed) {
        return static_cast<std::uint64_t>(pages) * kPagedKVPageSize >= tokens_needed;
    };
    if (session.text_pages == 0 || session.text_pages > text_pool.logical_page_capacity() ||
        !covers(session.text_pages, session.text_kv_valid) ||
        (backend != nullptr) != (session.backend_pages != 0) ||
        (backend != nullptr &&
         (session.backend_pages > backend->pool().logical_page_capacity() ||
          !covers(session.backend_pages, session.mtp_kv_valid)))) {
        throw std::invalid_argument("session snapshot page counts are out of range");
    }

    std::vector<TokenId> ledger = read_vector<TokenId>(reader, session.tokens, "ledger");
    if (ledger.size() != session.tokens) {
        throw std::invalid_argument("session snapshot ledger does not match its depth");
    }
    for (const TokenId id : ledger) {
        if (id < 0 || id >= TextConfig::token_domain) {
            throw std::invalid_argument("session snapshot ledger token is out of domain");
        }
    }
    std::vector<std::uint8_t> token_types =
        read_vector<std::uint8_t>(reader, session.tokens, "token type");
    std::array<std::vector<std::int32_t>, 3> positions;
    for (auto& axis : positions) {
        axis = read_vector<std::int32_t>(reader, session.tokens, "position");
    }
    std::vector<VisionItem> vision_items = read_vision_items(reader, session.tokens);
    if (token_types.size() != session.tokens || positions[0].size() != session.tokens ||
        positions[1].size() != session.tokens || positions[2].size() != session.tokens) {
        throw std::invalid_argument("session snapshot identity does not match its depth");
    }
    if (!vision_items.empty() && !vision_enabled) {
        throw std::invalid_argument("session snapshot holds media but Vision is disabled");
    }

    const std::uint8_t* tail_payload =
        session.tail_hidden_valid != 0 ? reader.payload(config.tail_hidden_bytes) : nullptr;
    const std::uint8_t* current_conv = reader.payload(conv_bytes * config.gdn_layers);
    const std::uint8_t* current_recurrent =
        reader.payload(recurrent_bytes * config.gdn_layers);
    const std::uint8_t* checkpoint_hidden    = nullptr;
    const std::uint8_t* checkpoint_conv      = nullptr;
    const std::uint8_t* checkpoint_recurrent = nullptr;
    if (session.turn_checkpoint_valid != 0) {
        checkpoint_hidden    = reader.payload(config.tail_hidden_bytes);
        checkpoint_conv      = reader.payload(conv_bytes * config.gdn_layers);
        checkpoint_recurrent = reader.payload(recurrent_bytes * config.gdn_layers);
    }
    const std::uint8_t* text_payload =
        reader.payload(config.text_page_bytes * session.text_pages);
    const std::uint8_t* backend_payload =
        session.backend_pages != 0
            ? reader.payload(config.backend_page_bytes * session.backend_pages)
            : nullptr;

    std::vector<HostTurnCheckpoint> checkpoint_ring;
    if (version == kSessionSnapshotVersionRing) {
        const std::uint32_t ring_count = reader.pod<std::uint32_t>();
        if (ring_count == 0 || ring_count > kSessionSnapshotMaxRingEntries) {
            throw std::invalid_argument("session snapshot checkpoint ring count is out of range");
        }
        checkpoint_ring.reserve(ring_count);
        std::uint32_t previous_frontier = 0;
        for (std::uint32_t index = 0; index < ring_count; ++index) {
            HostTurnCheckpoint entry;
            entry.frontier = reader.pod<std::uint32_t>();
            if (entry.frontier == 0 || entry.frontier <= previous_frontier ||
                entry.frontier > session.tokens) {
                throw std::invalid_argument(
                    "session snapshot checkpoint frontiers are inconsistent");
            }
            previous_frontier          = entry.frontier;
            const std::uint8_t* hidden = reader.payload(config.tail_hidden_bytes);
            const std::uint8_t* ring_conv = reader.payload(conv_bytes * config.gdn_layers);
            const std::uint8_t* ring_recurrent =
                reader.payload(recurrent_bytes * config.gdn_layers);
            entry.hidden.assign(hidden, hidden + config.tail_hidden_bytes);
            entry.conv.assign(ring_conv, ring_conv + conv_bytes * config.gdn_layers);
            entry.recurrent.assign(ring_recurrent,
                                   ring_recurrent + recurrent_bytes * config.gdn_layers);
            entry.session_digest = ledger_prefix_digest(
                std::span<const TokenId>(ledger.data(), entry.frontier));
            checkpoint_ring.push_back(std::move(entry));
        }
    }
    if (reader.remaining() != 0) {
        throw std::invalid_argument("session snapshot has trailing bytes");
    }
    // A server running without the ring (or with a smaller one) keeps only what it can plan
    // with; the newest entries survive.
    if (checkpoint_ring.size() > checkpoint_ring_capacity) {
        checkpoint_ring.erase(checkpoint_ring.begin(),
                              checkpoint_ring.end() -
                                  static_cast<std::ptrdiff_t>(checkpoint_ring_capacity));
    }

    if (!text_pool.can_reserve(session.text_pages) ||
        (backend != nullptr && !backend->pool().can_reserve(session.backend_pages))) {
        throw std::invalid_argument(
            "session snapshot does not fit the free KV capacity; evict other sessions first");
    }

    try {
        reserve_sequence_kv(sequence, session.text_pages, session.backend_pages);
        sequence.kv->text.materialize_pages(session.text_pages, device.stream);
        if (sequence.kv->backend) {
            sequence.kv->backend->materialize_pages(session.backend_pages, device.stream);
        }

        decoder->text_kv.pool().copy_pages_from_host(sequence.kv->text.page_ids(), text_payload,
                                                     device.stream);
        if (backend_payload != nullptr) {
            backend_kv_cache()->pool().copy_pages_from_host(sequence.kv->backend->page_ids(),
                                                            backend_payload, device.stream);
        }
        LinearAttentionStatePool& mutable_states = decoder->linear_attention;
        const auto restore_gdn_slot = [&](std::int32_t slot, const std::uint8_t* conv,
                                          const std::uint8_t* recurrent) {
            for (std::uint32_t layer = 0; layer < config.gdn_layers; ++layer) {
                const Tensor conv_state = mutable_states.conv_slot(layer, slot);
                CUDA_CHECK(cudaMemcpyAsync(conv_state.data, conv + layer * conv_bytes, conv_bytes,
                                           cudaMemcpyHostToDevice, device.stream));
                const Tensor recurrent_state = mutable_states.recurrent_slot(layer, slot);
                CUDA_CHECK(cudaMemcpyAsync(recurrent_state.data,
                                           recurrent + layer * recurrent_bytes, recurrent_bytes,
                                           cudaMemcpyHostToDevice, device.stream));
            }
        };
        restore_gdn_slot(current_slot, current_conv, current_recurrent);
        if (session.turn_checkpoint_valid != 0) {
            restore_gdn_slot(checkpoint_slot, checkpoint_conv, checkpoint_recurrent);
            CUDA_CHECK(cudaMemcpyAsync(sequence.turn_checkpoint_hidden.data, checkpoint_hidden,
                                       config.tail_hidden_bytes, cudaMemcpyHostToDevice,
                                       device.stream));
        }
        if (tail_payload != nullptr) {
            CUDA_CHECK(cudaMemcpyAsync(sequence.tail_hidden.data, tail_payload,
                                       config.tail_hidden_bytes, cudaMemcpyHostToDevice,
                                       device.stream));
        }
        device.synchronize();

        sequence.ledger = std::move(ledger);
        sequence.prefix_identity.restore(std::move(token_types), std::move(positions),
                                         std::move(vision_items));
        sequence.execution_frontier       = session.execution_frontier;
        sequence.ledger_frontier          = session.ledger_frontier;
        sequence.text_kv_valid            = session.text_kv_valid;
        sequence.mtp_kv_valid             = session.mtp_kv_valid;
        sequence.dflash_context_frontier  = 0;
        sequence.rope_delta               = session.rope_delta;
        sequence.mtp_draft_count          = 0;
        sequence.tail_hidden_valid        = session.tail_hidden_valid != 0;
        sequence.turn_checkpoint          = TurnCheckpoint{
                     .valid    = session.turn_checkpoint_valid != 0,
                     .frontier = session.turn_checkpoint_frontier,
        };
        sequence.checkpoint_ring = std::move(checkpoint_ring);
        discard_checkpoint_staging(sequence);
        sequence.kv->text.cancel_unmapped_entitlement();
        if (sequence.kv->backend) { sequence.kv->backend->cancel_unmapped_entitlement(); }
        sequence.retained = true;
        request.lifecycle = Lifecycle::Complete;
        request.pending   = {};
    } catch (...) {
        try {
            device.synchronize();
        } catch (...) {}
        clear_lane(sequence, request);
        throw;
    }
    return session.tokens;
}

} // namespace ninfer::targets::qwen3_6::detail::NINFER_QWEN36_RUNTIME_NS
