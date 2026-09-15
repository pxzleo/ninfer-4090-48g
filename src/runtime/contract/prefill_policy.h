#pragma once

#include "ninfer/types.h"

#include <algorithm>
#include <cstdint>
#include <numeric>

namespace ninfer::runtime {

struct PrefillChunkPolicy {
    std::uint32_t uncontended_chunk      = 0;
    std::uint32_t decode_contended_chunk = 0;
    std::uint32_t service_quantum        = 0;

    [[nodiscard]] std::uint32_t select(bool decode_ready) const noexcept {
        return decode_ready ? decode_contended_chunk : uncontended_chunk;
    }

    [[nodiscard]] std::uint64_t service_quanta(std::uint32_t processed_tokens) const noexcept {
        return processed_tokens == 0
                   ? 1ULL
                   : 1ULL + (static_cast<std::uint64_t>(processed_tokens) - 1ULL) /
                                service_quantum;
    }
};

[[nodiscard]] inline PrefillChunkPolicy
resolve_prefill_chunk_policy(const EngineOptions& options) noexcept {
    return PrefillChunkPolicy{
        .uncontended_chunk = std::min(options.prefill_chunk, options.max_context),
        .decode_contended_chunk =
            std::min(options.prefill_chunk_when_decoding, options.max_context),
        .service_quantum =
            std::min(std::gcd(options.prefill_chunk, options.prefill_chunk_when_decoding),
                     options.max_context),
    };
}

} // namespace ninfer::runtime
