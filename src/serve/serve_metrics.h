#pragma once

// Cumulative counters behind GET /metrics, in the flat `name value` subset of
// the Prometheus text format.
//
// The four llamacpp:-prefixed counters reproduce llama.cpp's --metrics
// semantics - computed prefill tokens (prefix-cache hits excluded) billed
// against prefill unit time, committed decode tokens against decode unit
// time - so scrapers that difference llama.cpp counters read this server
// without changes. They are sourced from the Engine's live per-unit totals,
// so they advance during a request like llama.cpp's do, not only at its
// completion. The ninfer:-prefixed series report what llama.cpp cannot:
// speculative draft/acceptance totals, prefix-cache reuse, and the current
// page-aligned Main KV occupancy/capacity.

#include "serve/generation_service.h"

#include <cstdint>
#include <map>
#include <mutex>
#include <string>
#include <vector>

namespace ninfer::serve {

class ServeMetrics {
public:
    // In-flight bookkeeping, hooked on the request start/done/error log
    // funnel. Entries are keyed by request id: end is idempotent and a
    // request that errors after starting is removed the same way as one that
    // completes, so no path can leak a permanently busy slot.
    void begin_request(std::uint64_t id, int prompt_tokens);
    void end_request(std::uint64_t id);

    // Oldest-first (id order = FIFO arrival order) prompt sizes of HTTP-layer
    // in-flight requests. This remains available for metrics/tests; /slots now
    // uses the Engine's boundary-consistent runtime lane snapshot.
    [[nodiscard]] std::vector<std::pair<std::uint64_t, int>> active_snapshot() const;

    // Accumulates one completed request. Called from the same funnel as the
    // request-done log line, so every protocol and both streaming modes count.
    void record(const GenerationOutcome& outcome);

    // Prompt/cache sizes of the most recent completed request, retained for compatibility tests
    // and consumers which still need request-level residue rather than physical KV occupancy.
    struct LastCompleted {
        int prompt_tokens = 0;
        int cached_tokens = 0;
    };
    [[nodiscard]] LastCompleted last_completed() const;

    // One complete Prometheus text body, without HTTP framing. In-flight
    // requests are split into processing/deferred against `max_concurrency`,
    // matching the FIFO scheduler's work-conserving behavior.
    // `live` supplies the four llamacpp token/seconds counters from the Engine's per-unit
    // totals, so scrapers see rates advance during a request; the completion-based sums this
    // class accumulates back the ninfer: series and the idle slot display.
    [[nodiscard]] std::string render(std::uint32_t max_concurrency,
                                     const ninfer::RuntimeStats& live) const;

private:
    mutable std::mutex mutex_;
    std::uint64_t requests_total_                    = 0;
    std::uint64_t prefix_cache_hit_tokens_total_     = 0;
    std::uint64_t speculative_draft_tokens_total_    = 0;
    std::uint64_t speculative_accepted_tokens_total_ = 0;
    LastCompleted last_completed_;
    std::map<std::uint64_t, int> active_;
};

} // namespace ninfer::serve
