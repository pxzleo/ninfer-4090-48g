#include "runtime/engine/request_memory.h"

#include "core/arena.h"
#include "core/device.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <memory>
#include <stdexcept>

namespace ninfer::runtime {
namespace {

bool is_power_of_two(std::size_t value) noexcept {
    return value != 0 && (value & (value - 1)) == 0;
}

} // namespace

class RequestMemory::Impl {
public:
    Impl(DeviceContext& context, std::size_t capacity) : device(context.device) {
        if (capacity != 0) {
            CUDA_CHECK(cudaSetDevice(device));
            arena = std::make_unique<DeviceArena>(capacity);
        }
    }

    ~Impl() {
        if (arena != nullptr) {
            (void)cudaSetDevice(device);
            arena.reset();
        }
    }

    struct Allocation {
        std::size_t begin     = 0;
        std::size_t offset    = 0;
        std::size_t end       = 0;
        std::size_t alignment = 1;
    };

    bool find_space(std::size_t bytes, std::size_t alignment, Allocation& result) const noexcept {
        if (arena == nullptr) { return false; }
        const std::size_t capacity = arena->capacity();
        std::size_t cursor = 0;
        for (;;) {
            const Allocation* next = nullptr;
            for (const auto& allocation : allocations) {
                if (allocation.end != 0 && allocation.begin >= cursor &&
                    (next == nullptr || allocation.begin < next->begin)) {
                    next = &allocation;
                }
            }
            const std::size_t limit = next != nullptr ? next->begin : capacity;
            const std::size_t padding = (alignment - cursor % alignment) % alignment;
            if (padding <= limit - cursor && bytes <= limit - cursor - padding) {
                result = {cursor, cursor + padding, cursor + padding + bytes, alignment};
                return true;
            }
            if (next == nullptr) { return false; }
            cursor = next->end;
        }
    }

    int device = 0;
    std::unique_ptr<DeviceArena> arena;
    std::array<Allocation, kMaximumConcurrency> allocations{};
    std::size_t active_bytes = 0;
    std::size_t peak_bytes   = 0;
};

RequestMemory::RequestMemory(DeviceContext& device, std::size_t frozen_capacity_bytes)
    : impl_(std::make_unique<Impl>(device, frozen_capacity_bytes)) {}

RequestMemory::~RequestMemory() = default;

bool RequestMemory::can_activate(std::uint32_t lane, std::size_t bytes,
                                std::size_t alignment) const {
    if (lane >= kMaximumConcurrency) { return false; }
    if (bytes == 0) { return alignment == 1; }
    if (!is_power_of_two(alignment) || alignment > kDeviceAllocationAlignment ||
        impl_->allocations[lane].end != 0) {
        return false;
    }
    Impl::Allocation allocation;
    return impl_->find_space(bytes, alignment, allocation);
}

void RequestMemory::activate(std::uint32_t lane, std::size_t bytes, std::size_t alignment) {
    if (lane >= kMaximumConcurrency) {
        throw std::out_of_range("request transient lane exceeds maximum concurrency");
    }
    if (bytes == 0) {
        if (alignment != 1) {
            throw std::invalid_argument("an empty transient region must use alignment one");
        }
        deactivate(lane);
        return;
    }
    if (!is_power_of_two(alignment) || alignment > kDeviceAllocationAlignment) {
        throw std::invalid_argument("unsupported transient region alignment");
    }
    if (impl_->allocations[lane].end != 0) {
        throw std::logic_error("request transient lane is already active");
    }
    Impl::Allocation allocation;
    if (!impl_->find_space(bytes, alignment, allocation)) {
        throw std::invalid_argument("request transient exceeds available frozen startup capacity");
    }
    impl_->allocations[lane] = allocation;
    impl_->active_bytes += allocation.end - allocation.begin;
    impl_->peak_bytes = std::max(impl_->peak_bytes, impl_->active_bytes);
}

void RequestMemory::deactivate(std::uint32_t lane) noexcept {
    if (lane >= kMaximumConcurrency) { return; }
    auto& allocation = impl_->allocations[lane];
    impl_->active_bytes -= allocation.end - allocation.begin;
    allocation = {};
}

TransientRegion RequestMemory::region(std::uint32_t lane) const {
    if (lane >= kMaximumConcurrency) {
        throw std::out_of_range("request transient lane exceeds maximum concurrency");
    }
    const auto& allocation = impl_->allocations[lane];
    if (allocation.end == 0) { return {}; }
    return {static_cast<std::byte*>(impl_->arena->base()) + allocation.offset,
            allocation.end - allocation.offset, allocation.alignment};
}

ArenaMemorySummary RequestMemory::summary() const noexcept {
    return ArenaMemorySummary{
        impl_->arena != nullptr ? impl_->arena->capacity() : 0,
        impl_->active_bytes,
        impl_->peak_bytes,
    };
}

void RequestMemory::reset_peak() noexcept { impl_->peak_bytes = impl_->active_bytes; }

} // namespace ninfer::runtime
