#pragma once

#include <cpp-httplib/httplib.h>

#include <atomic>
#include <chrono>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

namespace ninfer::serve {

class ClientDisconnected final : public std::runtime_error {
public:
    explicit ClientDisconnected(std::string message) : std::runtime_error(std::move(message)) {}
};

// Owned and called only by the chunked provider's socket-writing thread. The Engine wait's
// cancellation poll also runs on that thread, including while no model output is available.
class SseConnection {
public:
    using Clock = std::chrono::steady_clock;
    static constexpr auto keep_alive_interval = std::chrono::seconds(5);
    static constexpr std::string_view keep_alive = ": keep-alive\n\n";

    void generation_started() noexcept { phase_ = "generating"; }
    void finishing() noexcept { phase_ = "finishing"; }

    void write(httplib::DataSink& sink, std::atomic<bool>& cancelled, std::string_view item,
               Clock::time_point now = Clock::now()) {
        check_connection(sink, cancelled, now);
        if (!sink.write(item.data(), item.size())) { disconnect(cancelled, now); }
        last_sent_ = now;
    }

    void idle(httplib::DataSink& sink, std::atomic<bool>& cancelled,
              Clock::time_point now = Clock::now()) {
        check_connection(sink, cancelled, now);
        if (now - last_sent_ >= keep_alive_interval) { write(sink, cancelled, keep_alive, now); }
    }

private:
    void check_connection(httplib::DataSink& sink, std::atomic<bool>& cancelled,
                          Clock::time_point now) {
        if (cancelled.load(std::memory_order_acquire) ||
            (sink.is_writable && !sink.is_writable())) {
            disconnect(cancelled, now);
        }
    }

    [[noreturn]] void disconnect(std::atomic<bool>& cancelled, Clock::time_point now) {
        cancelled.store(true, std::memory_order_release);
        const auto silence = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_sent_);
        throw ClientDisconnected(std::string("client disconnected: phase=") + phase_ +
                                 " last_send_age_ms=" + std::to_string(silence.count()));
    }

    Clock::time_point last_sent_ = Clock::now();
    const char* phase_ = "awaiting_generation";
};

} // namespace ninfer::serve
