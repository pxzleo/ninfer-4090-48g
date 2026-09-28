#pragma once

#include "ninfer/types.h"
#include "runtime/contract/transient_region.h"

#include <cstddef>
#include <memory>

namespace ninfer {

struct DeviceContext;

namespace runtime {

// Owns one startup-frozen allocation shared by bounded, non-overlapping lane regions.
// Active regions never move; request-time device allocation or replacement is forbidden.
class RequestMemory {
public:
    static constexpr std::size_t kDeviceAllocationAlignment = 256;

    RequestMemory(DeviceContext& device, std::size_t frozen_capacity_bytes);
    ~RequestMemory();

    RequestMemory(const RequestMemory&)            = delete;
    RequestMemory& operator=(const RequestMemory&) = delete;
    RequestMemory(RequestMemory&&)                 = delete;
    RequestMemory& operator=(RequestMemory&&)      = delete;

    [[nodiscard]] bool can_activate(std::uint32_t lane, std::size_t bytes,
                                    std::size_t alignment) const;
    void activate(std::uint32_t lane, std::size_t bytes, std::size_t alignment);
    // An invalid lane is ignored by this noexcept cleanup operation.
    void deactivate(std::uint32_t lane) noexcept;

    [[nodiscard]] TransientRegion region(std::uint32_t lane) const;
    // Aggregate reserved bytes include each active region's leading alignment padding.
    [[nodiscard]] ArenaMemorySummary summary() const noexcept;
    void reset_peak() noexcept;

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace runtime
} // namespace ninfer
