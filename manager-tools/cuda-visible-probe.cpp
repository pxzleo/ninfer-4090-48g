#include <cstdio>

extern "C" {
typedef int CUdevice;
typedef struct { char bytes[16]; } CUuuid;
int cuInit(unsigned int flags);
int cuDeviceGetCount(int* count);
int cuDeviceGet(CUdevice* device, int ordinal);
int cuDeviceGetUuid(CUuuid* uuid, CUdevice device);
}

int main() {
    if (cuInit(0) != 0) return 2;
    int count = 0;
    if (cuDeviceGetCount(&count) != 0) return 3;
    std::printf("count=%d\n", count);
    for (int ordinal = 0; ordinal < count; ++ordinal) {
        CUdevice device = 0;
        CUuuid uuid{};
        if (cuDeviceGet(&device, ordinal) != 0 || cuDeviceGetUuid(&uuid, device) != 0) return 4;
        const unsigned char* b = reinterpret_cast<const unsigned char*>(uuid.bytes);
        std::printf("GPU-%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-"
                    "%02x%02x%02x%02x%02x%02x\n",
                    b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7],
                    b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]);
    }
    return 0;
}
