#include "core/device.h"
#include "runtime/engine/request_memory.h"

#include <cuda_runtime.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <stdexcept>

namespace {

bool cuda_unavailable(cudaError_t error) {
    return error == cudaErrorNoDevice || error == cudaErrorInsufficientDriver;
}

int expect(bool condition, const char* message) {
    if (condition) { return 0; }
    std::cerr << "FAIL: " << message << '\n';
    return 1;
}

template <class Exception, class Fn>
int expect_throws(Fn&& fn, const char* message) {
    try {
        fn();
    } catch (const Exception&) { return 0; }
    std::cerr << "FAIL: " << message << '\n';
    return 1;
}

} // namespace

int main() {
    int count                   = 0;
    const cudaError_t count_err = cudaGetDeviceCount(&count);
    if (cuda_unavailable(count_err) || (count_err == cudaSuccess && count == 0)) {
        std::cout << "SKIP: no usable CUDA device\n";
        return 77;
    }
    if (count_err != cudaSuccess) {
        std::cerr << "cudaGetDeviceCount failed: " << cudaGetErrorString(count_err) << '\n';
        return 1;
    }

    int failures = 0;
    ninfer::DeviceContext device(0);
    ninfer::runtime::RequestMemory memory(device, 1024);
    failures += expect(memory.summary().capacity_bytes == 1024,
                       "constructor did not freeze the requested capacity");

    memory.activate(0, 129, 1);
    const auto first = memory.region(0);
    memory.activate(1, 128, 256);
    const auto second = memory.region(1);
    failures += expect(first.data != nullptr && second.data == first.data + 256 &&
                           second.size == 128 && second.alignment == 256 &&
                           reinterpret_cast<std::uintptr_t>(second.data) % 256 == 0 &&
                           memory.summary().used_bytes == 384 &&
                           memory.summary().peak_used_bytes == 384,
                       "two lanes overlapped or reserved alignment padding was miscounted");
    std::array<unsigned char, 128> payload;
    payload.fill(0x5a);
    CUDA_CHECK(cudaMemcpy(second.data, payload.data(), payload.size(), cudaMemcpyHostToDevice));
    memory.activate(2, 640, 128);
    const auto third = memory.region(2);
    failures += expect(third.data == first.data + 384 && memory.summary().used_bytes == 1024 &&
                           !memory.can_activate(3, 1, 1),
                       "a full arena accepted another region");
    failures += expect_throws<std::invalid_argument>(
        [&] { memory.activate(3, 1, 1); }, "exhausted arena activation did not throw");
    failures += expect_throws<std::logic_error>(
        [&] { memory.activate(1, 128, 256); }, "active lane replacement did not throw");
    failures += expect(!memory.can_activate(1, 128, 256),
                       "can_activate accepted replacement of an active lane");

    memory.deactivate(0);
    std::array<unsigned char, 128> actual{};
    CUDA_CHECK(cudaMemcpy(actual.data(), second.data, actual.size(), cudaMemcpyDeviceToHost));
    failures += expect(memory.region(1).data == second.data && actual == payload &&
                           memory.region(2).data == third.data &&
                           memory.summary().used_bytes == 895 &&
                           memory.summary().peak_used_bytes == 1024,
                       "releasing the first lane moved or corrupted surviving regions");
    failures += expect(memory.can_activate(3, 129, 1) && !memory.can_activate(3, 130, 1),
                       "admission did not respect the available hole");
    memory.activate(3, 129, 1);
    failures += expect(memory.region(3).data == first.data,
                       "first-fit did not reuse the released leading hole");
    memory.deactivate(1);
    memory.activate(4, 255, 1);
    failures += expect(memory.region(4).data == first.data + 129 &&
                           memory.region(2).data == third.data &&
                           memory.region(3).data == first.data && memory.summary().used_bytes == 1024,
                       "a released middle hole was not reused without moving other lanes");
    CUDA_CHECK(cudaMemset(third.data, 0x3c, third.size));
    memory.deactivate(4);
    unsigned char third_payload = 0;
    CUDA_CHECK(cudaMemcpy(&third_payload, third.data, 1, cudaMemcpyDeviceToHost));
    failures += expect(third_payload == 0x3c && memory.region(2).data == third.data,
                       "releasing the middle lane corrupted another lane's payload");
    memory.reset_peak();
    failures += expect(memory.summary().peak_used_bytes == 769,
                       "reset_peak did not preserve aggregate current usage");

    failures += expect_throws<std::invalid_argument>(
        [&] { memory.activate(5, 128, 3); }, "invalid alignment did not throw");
    failures += expect_throws<std::invalid_argument>(
        [&] { memory.activate(5, 128, 512); }, "over-aligned region did not throw");
    failures += expect_throws<std::invalid_argument>(
        [&] { memory.activate(5, 0, 2); }, "empty over-aligned region did not throw");
    failures += expect_throws<std::out_of_range>(
        [&] { memory.activate(ninfer::kMaximumConcurrency, 1, 1); },
        "invalid activation lane did not throw");
    failures += expect_throws<std::out_of_range>(
        [&] { (void)memory.region(ninfer::kMaximumConcurrency); },
        "invalid region lane did not throw");
    failures += expect(!memory.can_activate(5, 128, 3) && !memory.can_activate(5, 128, 512) &&
                           !memory.can_activate(5, 0, 2) &&
                           !memory.can_activate(ninfer::kMaximumConcurrency, 0, 1) &&
                           memory.summary().used_bytes == 769,
                       "invalid admission changed usage or reported success");
    memory.activate(2, 0, 1);
    memory.deactivate(3);
    memory.reset_peak();
    failures += expect(memory.region(2).data == nullptr && memory.summary().used_bytes == 0 &&
                           memory.summary().peak_used_bytes == 0,
                       "empty activation or reset_peak did not clear released usage");
    memory.activate(ninfer::kMaximumConcurrency - 1, 1024, 256);
    failures += expect(memory.region(ninfer::kMaximumConcurrency - 1).data == first.data,
                       "last lane could not reuse the complete frozen arena");

    ninfer::runtime::RequestMemory empty(device, 0);
    failures += expect(empty.can_activate(0, 0, 1) && !empty.can_activate(0, 1, 1),
                       "zero-capacity admission reported the wrong state");
    empty.activate(0, 0, 1);
    failures += expect(empty.region(0).data == nullptr && empty.summary().capacity_bytes == 0,
                       "zero-capacity request memory exposed a device allocation");
    failures += expect_throws<std::invalid_argument>(
        [&] { empty.activate(0, 1, 1); }, "nonempty zero-capacity activation did not throw");

    if (failures == 0) { std::cout << "ok\n"; }
    return failures == 0 ? 0 : 1;
}
