#include "serve/sse_connection.h"

#include <iostream>
#include <string>
#include <thread>

namespace {
using namespace ninfer::serve;
using namespace std::chrono_literals;

int check(bool condition, const char* message) {
    if (condition) { return 0; }
    std::cerr << message << '\n';
    return 1;
}
} // namespace

int main() {
    int failures = 0;
    SseConnection connection;
    std::atomic<bool> cancelled{false};
    httplib::DataSink sink;
    std::string wire;
    const auto writer_thread = std::this_thread::get_id();
    sink.is_writable = [] { return true; };
    sink.write = [&](const char* data, std::size_t size) {
        failures += check(std::this_thread::get_id() == writer_thread,
                          "SSE writes moved off the socket writer thread");
        wire.append(data, size);
        return true;
    };
    const auto start = SseConnection::Clock::now();
    connection.write(sink, cancelled, "data: start\n\n", start);
    connection.idle(sink, cancelled, start + 4999ms);
    failures += check(wire == "data: start\n\n", "heartbeat was emitted before idle deadline");
    connection.idle(sink, cancelled, start + 5s);
    connection.idle(sink, cancelled, start + 10s);
    failures += check(wire == "data: start\n\n: keep-alive\n\n: keep-alive\n\n",
                      "idle stream did not emit periodic SSE comments");
    connection.generation_started();
    connection.write(sink, cancelled, "data: token\n\n", start + 11s);
    const auto after_content = wire;
    connection.idle(sink, cancelled, start + 15s);
    failures += check(wire == after_content, "content write did not reset heartbeat deadline");
    sink.write = [](const char*, std::size_t) { return false; };
    try {
        connection.idle(sink, cancelled, start + 16s);
        failures += check(false, "failed heartbeat write did not detect disconnect");
    } catch (const ClientDisconnected& error) {
        failures += check(cancelled.load() && std::string(error.what()).find(
                              "phase=generating last_send_age_ms=5000") != std::string::npos,
                          "disconnect omitted generation phase or last successful write age");
    }
    SseConnection waiting;
    cancelled = false;
    sink.is_writable = [] { return false; };
    try {
        waiting.idle(sink, cancelled);
        failures += check(false, "idle stream did not notice an unwritable connection");
    } catch (const ClientDisconnected& error) {
        failures += check(cancelled.load() && std::string(error.what()).find(
                              "phase=awaiting_generation") != std::string::npos,
                          "pre-token disconnect did not identify its waiting phase");
    }

    // Real HTTP stream: no generation or token callback for two heartbeat intervals. A client
    // whose read timeout is shorter than the wait must stay connected on the SSE comments alone.
    httplib::Server server;
    std::atomic<bool> provider_ok{true};
    server.Post("/stream", [&](const httplib::Request&, httplib::Response& response) {
        response.set_chunked_content_provider(
            "text/event-stream", [&](std::size_t, httplib::DataSink& output) {
                SseConnection idle;
                std::atomic<bool> stopped{false};
                const auto until = SseConnection::Clock::now() + 11s;
                try {
                    while (SseConnection::Clock::now() < until) {
                        idle.idle(output, stopped);
                        std::this_thread::sleep_for(10ms);
                    }
                    output.done();
                    return true;
                } catch (const ClientDisconnected&) {
                    provider_ok = false;
                    return false;
                }
            });
    });
    const int port = server.bind_to_any_port("127.0.0.1");
    if (port < 0) { return check(false, "could not bind CPU SSE integration server"); }
    std::thread listener([&] { server.listen_after_bind(); });
    server.wait_until_ready();
    httplib::Client client("127.0.0.1", port);
    client.set_read_timeout(6, 0);
    httplib::Request request;
    request.method = "POST";
    request.path = "/stream";
    request.body = "{}";
    std::string received;
    request.content_receiver = [&](const char* data, std::size_t size, std::uint64_t,
                                   std::uint64_t) {
        received.append(data, size);
        return true;
    };
    const auto result = client.send(request);
    server.stop();
    listener.join();
    failures += check(result && result->status == 200 && provider_ok.load(),
                      "HTTP stream timed out while waiting without generated tokens");
    failures += check(received == ": keep-alive\n\n: keep-alive\n\n",
                      "waiting HTTP stream fabricated content or malformed heartbeat frames");
    return failures == 0 ? 0 : 1;
}
