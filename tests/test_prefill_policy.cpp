#include "runtime/contract/prefill_policy.h"

#include <iostream>

namespace {

int check(bool condition, const char* message) {
    if (condition) { return 0; }
    std::cerr << message << '\n';
    return 1;
}

} // namespace

int main() {
    int failures = 0;

    ninfer::EngineOptions recommended;
    recommended.max_context                 = 262144;
    recommended.prefill_chunk               = 1024;
    recommended.prefill_chunk_when_decoding = 256;
    const auto adaptive = ninfer::runtime::resolve_prefill_chunk_policy(recommended);
    failures += check(adaptive.select(false) == 1024 && adaptive.select(true) == 256,
                      "decode membership did not select the expected prefill extent");
    failures += check(adaptive.service_quantum == 256 && adaptive.service_quanta(1024) == 4,
                      "recommended adaptive profile has inconsistent service accounting");

    ninfer::EngineOptions non_divisible = recommended;
    non_divisible.prefill_chunk               = 384;
    non_divisible.prefill_chunk_when_decoding = 256;
    const auto mixed = ninfer::runtime::resolve_prefill_chunk_policy(non_divisible);
    failures += check(mixed.service_quantum == 128 &&
                          2 * mixed.service_quanta(384) == mixed.service_quanta(768),
                      "non-divisible prefill extents over-consume projected service work");

    return failures == 0 ? 0 : 1;
}
