#include "runtime/engine/admission_policy.h"

#include <algorithm>
#include <array>
#include <iostream>

namespace {

int check(bool condition, const char* message) {
    if (condition) { return 0; }
    std::cerr << message << '\n';
    return 1;
}

int test_retained_lane_admission() {
    using ninfer::runtime::LaneAdmissionSnapshot;
    using ninfer::runtime::select_admission_lane;
    using ninfer::runtime::select_retained_eviction_lane;

    // Real 760000-token pool incident: the matching lane needs 32064 more tokens,
    // but only 31296 remain. Replacing lane 6 fits directly and would lose two sessions.
    std::array<LaneAdmissionSnapshot, 8> lanes{
        LaneAdmissionSnapshot{.lane = 0, .retained = true, .retained_prompt_tokens = 59323},
        LaneAdmissionSnapshot{.lane = 1, .retained = true, .retained_prompt_tokens = 22359},
        LaneAdmissionSnapshot{.lane = 2, .retained = true, .retained_prompt_tokens = 123364,
                              .reusable_prompt_tokens = 121921},
        LaneAdmissionSnapshot{.lane = 3, .retained = true, .retained_prompt_tokens = 22276},
        LaneAdmissionSnapshot{.lane = 4, .retained = true, .retained_prompt_tokens = 233213},
        LaneAdmissionSnapshot{.lane = 5, .processing = true, .retained_prompt_tokens = 32550},
        LaneAdmissionSnapshot{.lane = 6, .retained = true, .retained_prompt_tokens = 154648},
        LaneAdmissionSnapshot{.lane = 7, .processing = true, .retained_prompt_tokens = 16751},
    };
    const auto pages = [](std::uint32_t tokens) { return (tokens + 63U) / 64U; };
    constexpr std::uint32_t free_pages = 31296 / 64;
    constexpr std::uint32_t requested_tokens = 123399 + 32000 - 1;
    std::uint32_t reclaimable_pages = 0;
    for (const auto& lane : lanes) {
        if (!lane.processing && lane.retained) {
            reclaimable_pages += pages(lane.retained_prompt_tokens);
        }
    }
    for (auto& lane : lanes) {
        if (lane.processing) { continue; }
        lane.direct_admission = pages(requested_tokens) <=
            free_pages + pages(lane.retained_prompt_tokens);
        lane.admission_after_eviction = pages(requested_tokens) <= free_pages + reclaimable_pages;
    }

    int failures = 0;
    auto selected = select_admission_lane(lanes);
    failures += check(selected && selected->lane == 2 && selected->evict_retained,
                      "direct cold admission bypassed a feasible retained continuation");
    auto victim = select_retained_eviction_lane(lanes, 2);
    failures += check(victim && *victim == 3,
                      "eviction did not choose the smallest idle non-target cache");
    failures += check(free_pages + pages(lanes[3].retained_prompt_tokens) +
                          pages(lanes[2].retained_prompt_tokens) >= pages(requested_tokens),
                      "one small idle-cache eviction did not resolve the reproduced deficit");

    lanes[3].retained = false;
    victim = select_retained_eviction_lane(lanes, 2);
    failures += check(victim && *victim == 1,
                      "repeated eviction did not advance to the next smallest idle cache");
    victim = select_retained_eviction_lane(lanes, 1);
    failures += check(victim && *victim == 0,
                      "eviction destroyed the protected continuation or an active request");

    lanes[2].admission_after_eviction = false;
    selected = select_admission_lane(lanes);
    failures += check(selected && selected->lane == 6 && !selected->evict_retained,
                      "infeasible reuse prevented a feasible direct admission");
    lanes[2].admission_after_eviction = true;
    lanes[6].reusable_prompt_tokens = lanes[2].reusable_prompt_tokens;
    selected = select_admission_lane(lanes);
    failures += check(selected && selected->lane == 6 && !selected->evict_retained,
                      "equal reuse caused unnecessary additional eviction");
    lanes[6].reusable_prompt_tokens = 0;
    std::reverse(lanes.begin(), lanes.end());
    selected = select_admission_lane(lanes);
    failures += check(selected && selected->lane == 2 && selected->evict_retained,
                      "retained continuation selection depended on lane enumeration order");
    for (auto& lane : lanes) { lane.processing = true; }
    failures += check(!select_admission_lane(lanes) && !select_retained_eviction_lane(lanes, 2),
                      "active lanes were admitted into or evicted");
    return failures;
}

} // namespace

int main() {
    using ninfer::runtime::ActiveAdmissionSnapshot;
    using ninfer::runtime::AdmissionResources;
    using ninfer::runtime::BackfillClass;

    int failures = test_retained_lane_admission();
    const AdmissionResources capacity{
        .active_lanes     = 4,
        .main_kv_pages    = 160,
        .backend_kv_pages = 128,
    };
    const AdmissionResources head{
        .active_lanes     = 1,
        .main_kv_pages    = 64,
        .backend_kv_pages = 48,
    };
    std::array<ActiveAdmissionSnapshot, 2> incumbents{
        ActiveAdmissionSnapshot{
            .request_id            = 1,
            .resources             = {1, 64, 32},
            .remaining_work_quanta = 100,
        },
        ActiveAdmissionSnapshot{
            .request_id            = 2,
            .resources             = {1, 48, 64},
            .remaining_work_quanta = 20,
        },
    };

    const auto protection = ninfer::runtime::make_admission_protection(
        7, 10, head, std::span<const ActiveAdmissionSnapshot>(incumbents), capacity);
    failures += check(protection.donor_count == 1 && protection.donor_ids[0] == 2 &&
                          protection.temporal_credit == 20,
                      "release frontier did not select the earliest sufficient incumbent");
    failures += check(ninfer::runtime::protection_frontier_distance(protection, incumbents) == 20,
                      "frontier distance did not follow the frozen donor");

    const AdmissionResources persistent_candidate{1, 24, 40};
    failures += check(ninfer::runtime::persistent_backfill_is_safe(protection, incumbents,
                                                                   persistent_candidate, capacity),
                      "future resource surplus rejected a persistent-safe backfill");
    failures += check(!ninfer::runtime::persistent_backfill_is_safe(
                          protection, incumbents, AdmissionResources{1, 40, 60}, capacity),
                      "persistent backfill borrowed protected future capacity");

    std::array<ActiveAdmissionSnapshot, 3> with_persistent{
        incumbents[0],
        incumbents[1],
        ActiveAdmissionSnapshot{
            .request_id            = 3,
            .resources             = persistent_candidate,
            .remaining_work_quanta = 50,
            .backfill_epoch        = 7,
            .backfill_class        = BackfillClass::Persistent,
        },
    };
    failures += check(!ninfer::runtime::persistent_backfill_is_safe(
                          protection, with_persistent, AdmissionResources{1, 9, 9}, capacity),
                      "persistent ledger failed to accumulate earlier backfills");

    std::array<ActiveAdmissionSnapshot, 2> after_donor{
        incumbents[0],
        ActiveAdmissionSnapshot{
            .request_id            = 4,
            .resources             = {1, 32, 64},
            .remaining_work_quanta = 8,
            .backfill_epoch        = 7,
            .backfill_class        = BackfillClass::Temporal,
        },
    };
    failures += check(ninfer::runtime::protection_frontier_distance(protection, after_donor) == 0,
                      "later temporal work changed the frozen frontier");
    failures += check(
        ninfer::runtime::protected_head_safe_without_temporal(protection, after_donor, capacity),
        "released frontier did not mature behind a temporal borrower");

    failures += check(
        !ninfer::runtime::admission_resources_fit(AdmissionResources{1, 161, 1}, capacity) &&
            !ninfer::runtime::admission_resources_fit(AdmissionResources{1, 1, 129}, capacity),
        "independent KV pools were incorrectly treated as interchangeable capacity");

    if (failures == 0) { std::cout << "ok\n"; }
    return failures == 0 ? 0 : 1;
}
