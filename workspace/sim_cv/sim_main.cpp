#include "Vaisl_soc.h"
#include "sha256.h"
#include "verilated.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#ifndef AISL_RTL_SHA256
#define AISL_RTL_SHA256 "unavailable"
#endif

namespace fs = std::filesystem;

namespace {

constexpr std::uint32_t kMemoryBytes = 64u * 1024u * 1024u;
constexpr std::uint32_t kWadAddress = 0x02000000u;
constexpr std::uint32_t kInputAddress = 0x03c00000u;

struct Config {
    fs::path firmware;
    fs::path wad;
    fs::path inputs;
    fs::path frames_dir;
    fs::path result_file;
    fs::path uart_log;
    std::uint32_t width = 320;
    std::uint32_t height = 200;
    std::uint32_t frame_count = 120;
    std::uint32_t frame_warmup = 64;
    std::uint32_t skill = 2;
    std::uint32_t episode = 1;
    std::uint32_t map = 1;
    std::uint32_t memory_latency = 0;
    std::uint32_t reset_cycles = 8;
    std::uint32_t trace_sample_limit = 128;
    std::uint32_t cycle_trace_stride = 1024;
    std::uint32_t execution_trace_stride = 1;
    std::uint64_t max_cycles = 100000000000ull;
};

struct InputEvent {
    std::uint32_t tic;
    std::uint32_t keycode;
    std::uint32_t pressed;
};

struct RetireSample {
    std::uint64_t cycle;
    std::uint64_t order;
    std::uint32_t instruction;
    std::uint32_t pc;
    std::uint32_t next_pc;
    std::uint32_t memory_address;
    std::uint32_t memory_read_data;
    std::uint32_t memory_write_data;
    std::uint32_t register_write_data;
    std::uint8_t memory_read_mask;
    std::uint8_t memory_write_mask;
    std::uint8_t register_write_address;
    bool trapped;
};

struct FrameArtifact {
    std::uint32_t index;
    fs::path path;
    std::string sha256;
};

struct Report {
    bool booted = false;
    bool doom_started = false;
    bool finished = false;
    bool failed = false;
    bool trapped = false;
    bool success = false;
    std::string exit_reason = "not_started";
    std::string error;
    std::uint64_t cycles = 0;
    std::uint64_t boot_cycle = 0;
    std::uint64_t doom_started_cycle = 0;
    std::uint64_t first_capture_cycle = 0;
    std::uint64_t finish_cycle = 0;
    std::uint64_t retired_instructions = 0;
    std::uint64_t native_trace_events = 0;
    std::uint64_t cycle_trace_samples = 0;
    std::uint64_t native_trace_hash_samples = 0;
    std::uint64_t retire_trace_hash_samples = 0;
    std::uint32_t input_count = 0;
    std::uint32_t firmware_wad_size = 0;
    std::uint32_t stat_simulation_frames = 0;
    std::uint32_t stat_game_tics = 0;
    std::uint32_t stat_captured_frames = 0;
    std::uint32_t stat_exit_code = 0;
    std::string firmware_sha256;
    std::string simulator_sha256;
    std::string rtl_sources_sha256 = AISL_RTL_SHA256;
    std::string wad_sha256;
    std::string input_text_sha256;
    std::string input_records_sha256;
    std::string cycle_trace_sha256;
    std::string native_trace_sha256;
    std::string retire_trace_sha256;
    std::string frames_sha256;
    std::string uart_sha256;
    std::string uart;
    std::vector<RetireSample> retire_samples;
    std::optional<RetireSample> last_retire_sample;
    std::vector<FrameArtifact> frames;
};

std::string json_escape(const std::string& input) {
    std::ostringstream out;
    for (unsigned char character : input) {
        switch (character) {
        case '\"': out << "\\\""; break;
        case '\\': out << "\\\\"; break;
        case '\b': out << "\\b"; break;
        case '\f': out << "\\f"; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (character < 0x20) {
                out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                    << static_cast<unsigned>(character) << std::dec;
            } else {
                out << static_cast<char>(character);
            }
        }
    }
    return out.str();
}

std::string hex32(std::uint32_t value) {
    std::ostringstream out;
    out << "0x" << std::hex << std::setw(8) << std::setfill('0') << value;
    return out.str();
}

std::string absolute_string(const fs::path& path) {
    return fs::absolute(path).lexically_normal().string();
}

std::optional<std::string> environment(const char* name) {
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') {
        return std::nullopt;
    }
    return std::string(value);
}

std::uint64_t parse_u64(const std::string& text, const std::string& description) {
    std::size_t consumed = 0;
    unsigned long long value = 0;
    try {
        value = std::stoull(text, &consumed, 0);
    } catch (const std::exception&) {
        throw std::runtime_error("invalid " + description + ": " + text);
    }
    if (consumed != text.size()) {
        throw std::runtime_error("invalid " + description + ": " + text);
    }
    return static_cast<std::uint64_t>(value);
}

std::uint32_t parse_u32(const std::string& text, const std::string& description) {
    const std::uint64_t value = parse_u64(text, description);
    if (value > std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error(description + " is outside uint32_t: " + text);
    }
    return static_cast<std::uint32_t>(value);
}

void apply_environment(Config& config) {
    if (auto value = environment("AISL_FIRMWARE_FILE")) config.firmware = *value;
    if (auto value = environment("AISL_WAD_FILE")) config.wad = *value;
    if (auto value = environment("AISL_INPUT_FILE")) config.inputs = *value;
    if (auto value = environment("AISL_FRAME_DIR")) config.frames_dir = *value;
    if (auto value = environment("AISL_RESULT_FILE")) config.result_file = *value;
    if (auto value = environment("AISL_UART_LOG")) config.uart_log = *value;
    if (auto value = environment("AISL_FRAME_WIDTH")) config.width = parse_u32(*value, "frame width");
    if (auto value = environment("AISL_FRAME_HEIGHT")) config.height = parse_u32(*value, "frame height");
    if (auto value = environment("AISL_FRAME_COUNT")) config.frame_count = parse_u32(*value, "frame count");
    if (auto value = environment("AISL_FRAME_WARMUP")) config.frame_warmup = parse_u32(*value, "frame warmup");
    if (auto value = environment("AISL_SKILL")) config.skill = parse_u32(*value, "skill");
    if (auto value = environment("AISL_EPISODE")) config.episode = parse_u32(*value, "episode");
    if (auto value = environment("AISL_MAP")) config.map = parse_u32(*value, "map");
    if (auto value = environment("AISL_MEMORY_LATENCY")) config.memory_latency = parse_u32(*value, "memory latency");
    if (auto value = environment("AISL_CYCLE_TRACE_STRIDE")) config.cycle_trace_stride = parse_u32(*value, "cycle trace stride");
    if (auto value = environment("AISL_EXECUTION_TRACE_STRIDE")) config.execution_trace_stride = parse_u32(*value, "execution trace stride");
    if (auto value = environment("AISL_MAX_CYCLES")) config.max_cycles = parse_u64(*value, "maximum cycles");
}

void print_help(const char* executable) {
    std::cout
        << "Usage: " << executable << " [options]\n"
        << "  --firmware FILE       flat firmware binary loaded at 0x00000000\n"
        << "  --wad FILE            WAD bytes loaded at 0x02000000\n"
        << "  --inputs FILE         textual input schedule encoded at 0x03c00000\n"
        << "  --frames-dir DIR      destination for frame-%06u.rgb\n"
        << "  --result FILE         JSON evidence report\n"
        << "  --uart-log FILE       raw UART output (defaults beside result)\n"
        << "  --width N             framebuffer width (default 320)\n"
        << "  --height N            framebuffer height (default 200)\n"
        << "  --frame-count N       required captured frames (default 120)\n"
        << "  --warmup N            firmware-visible warmup count (default 64)\n"
        << "  --skill N             Doom skill (default 2)\n"
        << "  --episode N           Doom episode (default 1)\n"
        << "  --map N               Doom map (default 1)\n"
        << "  --memory-latency N    deterministic full wait cycles (default 0)\n"
        << "  --max-cycles N        stop honestly at this cycle (default 100000000000)\n"
        << "  --trace-samples N     bounded retirement samples in result (default 128)\n"
        << "  --cycle-trace-stride N  hash one full-state checkpoint every N cycles (default 1024)\n"
        << "  --execution-trace-stride N  hash every Nth diagnostic event (default 1: full)\n";
}

Config parse_arguments(int argc, char** argv) {
    Config config;
    apply_environment(config);
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        auto value = [&](const std::string& option) -> std::string {
            if (++i >= argc) {
                throw std::runtime_error("missing value for " + option);
            }
            return argv[i];
        };
        if (argument == "--help" || argument == "-h") {
            print_help(argv[0]);
            std::exit(0);
        } else if (argument == "--firmware") {
            config.firmware = value(argument);
        } else if (argument == "--wad") {
            config.wad = value(argument);
        } else if (argument == "--inputs") {
            config.inputs = value(argument);
        } else if (argument == "--frames-dir") {
            config.frames_dir = value(argument);
        } else if (argument == "--result") {
            config.result_file = value(argument);
        } else if (argument == "--uart-log") {
            config.uart_log = value(argument);
        } else if (argument == "--width") {
            config.width = parse_u32(value(argument), "frame width");
        } else if (argument == "--height") {
            config.height = parse_u32(value(argument), "frame height");
        } else if (argument == "--frame-count") {
            config.frame_count = parse_u32(value(argument), "frame count");
        } else if (argument == "--warmup") {
            config.frame_warmup = parse_u32(value(argument), "warmup count");
        } else if (argument == "--skill") {
            config.skill = parse_u32(value(argument), "skill");
        } else if (argument == "--episode") {
            config.episode = parse_u32(value(argument), "episode");
        } else if (argument == "--map") {
            config.map = parse_u32(value(argument), "map");
        } else if (argument == "--memory-latency") {
            config.memory_latency = parse_u32(value(argument), "memory latency");
        } else if (argument == "--max-cycles") {
            config.max_cycles = parse_u64(value(argument), "maximum cycles");
        } else if (argument == "--trace-samples") {
            config.trace_sample_limit = parse_u32(value(argument), "trace sample limit");
        } else if (argument == "--cycle-trace-stride") {
            config.cycle_trace_stride = parse_u32(value(argument), "cycle trace stride");
        } else if (argument == "--execution-trace-stride") {
            config.execution_trace_stride = parse_u32(value(argument), "execution trace stride");
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }

    if (config.firmware.empty()) throw std::runtime_error("firmware path is required");
    if (config.wad.empty()) throw std::runtime_error("WAD path is required");
    if (config.inputs.empty()) throw std::runtime_error("input schedule path is required");
    if (config.frames_dir.empty()) throw std::runtime_error("frame directory is required");
    if (config.result_file.empty()) throw std::runtime_error("result path is required");
    if (config.uart_log.empty()) config.uart_log = config.result_file.string() + ".uart.log";
    if (config.width == 0 || config.height == 0) throw std::runtime_error("frame dimensions must be non-zero");
    if (config.max_cycles == 0) throw std::runtime_error("maximum cycles must be non-zero");
    if (config.memory_latency > 1000000u) throw std::runtime_error("memory latency is unreasonably large");
    if (config.cycle_trace_stride == 0) throw std::runtime_error("cycle trace stride must be non-zero");
    if (config.execution_trace_stride == 0) throw std::runtime_error("execution trace stride must be non-zero");
    if (auto format = environment("AISL_FRAME_FORMAT")) {
        if (*format != "rgb888") throw std::runtime_error("unsupported AISL_FRAME_FORMAT: " + *format);
    }
    return config;
}

bool starts_with_component(const fs::path& relative, const std::string& component) {
    const auto iterator = relative.begin();
    return iterator != relative.end() && iterator->string() == component;
}

void reject_protected_path(const fs::path& path, const std::string& purpose) {
    const fs::path repository = fs::weakly_canonical(fs::current_path());
    const fs::path resolved = fs::weakly_canonical(path);
    const fs::path relative = resolved.lexically_relative(repository);
    if (!relative.empty() && (starts_with_component(relative, "ground_truth") ||
                              starts_with_component(relative, "lab"))) {
        throw std::runtime_error(purpose + " may not access protected repository path: " + resolved.string());
    }
}

std::vector<std::uint8_t> read_file(const fs::path& path, const std::string& purpose) {
    reject_protected_path(path, purpose);
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open " + purpose + ": " + path.string());
    input.seekg(0, std::ios::end);
    const std::streamoff length = input.tellg();
    if (length < 0) throw std::runtime_error("cannot size " + purpose + ": " + path.string());
    input.seekg(0, std::ios::beg);
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(length));
    if (!bytes.empty()) {
        input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
        if (!input) throw std::runtime_error("cannot read " + purpose + ": " + path.string());
    }
    return bytes;
}

std::string hash_bytes(const std::vector<std::uint8_t>& bytes) {
    Sha256 hash;
    if (!bytes.empty()) hash.update(bytes.data(), bytes.size());
    return hash.hex_digest();
}

std::uint32_t keycode_for(std::string token) {
    std::transform(token.begin(), token.end(), token.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    static const std::unordered_map<std::string, std::uint32_t> named_keys = {
        {"right", 0xaeu}, {"left", 0xacu}, {"up", 0xadu}, {"down", 0xafu},
        {"strafe_left", 0xa0u}, {"strafe_right", 0xa1u},
        {"use", 0xa2u}, {"fire", 0xa3u}, {"shift", 0xb6u},
        {"escape", 27u}, {"enter", 13u}, {"tab", 9u}, {"space", 32u},
    };
    if (const auto found = named_keys.find(token); found != named_keys.end()) {
        return found->second;
    }
    if (token.size() == 1 && static_cast<unsigned char>(token[0]) < 0x80) {
        return static_cast<unsigned char>(token[0]);
    }
    if (!token.empty() && (std::isdigit(static_cast<unsigned char>(token[0])) ||
                           (token.size() > 2 && token[0] == '0' && token[1] == 'x'))) {
        return parse_u32(token, "input keycode");
    }
    throw std::runtime_error("unknown input key token: " + token);
}

std::vector<InputEvent> parse_events(const std::vector<std::uint8_t>& bytes) {
    const std::string text(bytes.begin(), bytes.end());
    std::istringstream input(text);
    std::vector<InputEvent> events;
    std::string line;
    std::uint32_t previous_tic = 0;
    bool have_previous = false;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (const auto comment = line.find('#'); comment != std::string::npos) {
            line.erase(comment);
        }
        std::istringstream fields(line);
        std::string tic_text;
        std::string key_text;
        std::string pressed_text;
        if (!(fields >> tic_text)) continue;
        if (!(fields >> key_text >> pressed_text)) {
            throw std::runtime_error("malformed input event at line " + std::to_string(line_number));
        }
        std::string extra;
        if (fields >> extra) {
            throw std::runtime_error("extra input field at line " + std::to_string(line_number));
        }
        InputEvent event{
            parse_u32(tic_text, "input tic at line " + std::to_string(line_number)),
            keycode_for(key_text),
            parse_u32(pressed_text, "pressed flag at line " + std::to_string(line_number)),
        };
        if (event.pressed > 1) {
            throw std::runtime_error("pressed flag must be 0 or 1 at line " + std::to_string(line_number));
        }
        if (have_previous && event.tic < previous_tic) {
            throw std::runtime_error("input tics decrease at line " + std::to_string(line_number));
        }
        previous_tic = event.tic;
        have_previous = true;
        events.push_back(event);
    }
    return events;
}

void append_le32(std::vector<std::uint8_t>& bytes, std::uint32_t value) {
    bytes.push_back(static_cast<std::uint8_t>(value));
    bytes.push_back(static_cast<std::uint8_t>(value >> 8));
    bytes.push_back(static_cast<std::uint8_t>(value >> 16));
    bytes.push_back(static_cast<std::uint8_t>(value >> 24));
}

std::vector<std::uint8_t> encode_events(const std::vector<InputEvent>& events) {
    std::vector<std::uint8_t> bytes;
    bytes.reserve(events.size() * 12);
    for (const InputEvent& event : events) {
        append_le32(bytes, event.tic);
        append_le32(bytes, event.keycode);
        append_le32(bytes, event.pressed);
    }
    return bytes;
}

void hash_u8(Sha256& hash, std::uint8_t value) { hash.update(&value, sizeof(value)); }

void hash_u32(Sha256& hash, std::uint32_t value) {
    std::array<std::uint8_t, 4> bytes{
        static_cast<std::uint8_t>(value), static_cast<std::uint8_t>(value >> 8),
        static_cast<std::uint8_t>(value >> 16), static_cast<std::uint8_t>(value >> 24),
    };
    hash.update(bytes.data(), bytes.size());
}

void hash_u64(Sha256& hash, std::uint64_t value) {
    std::array<std::uint8_t, 8> bytes{};
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        bytes[i] = static_cast<std::uint8_t>(value >> (i * 8));
    }
    hash.update(bytes.data(), bytes.size());
}

class MemoryBus {
public:
    explicit MemoryBus(std::uint32_t latency) : memory_(kMemoryBytes, 0) {
        if (latency != 0) {
            throw std::runtime_error(
                "dual-port OBI model supports zero wait states (one-cycle responses) only");
        }
    }

    void load(std::uint32_t address, const std::vector<std::uint8_t>& bytes, const std::string& purpose) {
        if (bytes.size() > memory_.size() || address > memory_.size() - bytes.size()) {
            throw std::runtime_error(purpose + " does not fit in external memory");
        }
        std::copy(bytes.begin(), bytes.end(), memory_.begin() + address);
    }

    std::uint32_t read_word(std::uint32_t address) const {
        const std::uint32_t aligned = address & ~3u;
        if (aligned > memory_.size() - 4) throw std::runtime_error("memory read is out of range");
        return static_cast<std::uint32_t>(memory_[aligned]) |
               (static_cast<std::uint32_t>(memory_[aligned + 1]) << 8) |
               (static_cast<std::uint32_t>(memory_[aligned + 2]) << 16) |
               (static_cast<std::uint32_t>(memory_[aligned + 3]) << 24);
    }

    // Both ports accept one request per cycle. Responses are returned on the
    // following cycle, matching a synchronous dual-port SRAM/OBI subsystem.
    void drive_responses(Vaisl_soc& top) const {
        top.instr_gnt = 1;
        top.data_gnt = 1;
        top.instr_rvalid = instruction_response_.active;
        top.instr_rdata = instruction_response_.active
            ? read_word(instruction_response_.address) : 0;
        top.data_rvalid = data_response_.active;
        top.data_rdata = data_response_.read_data;
    }

    void capture_requests(const Vaisl_soc& top) {
        next_instruction_ = {};
        next_data_ = {};
        if (!top.resetn) return;

        if (top.instr_req) {
            validate_address(top.instr_addr, "instruction");
            next_instruction_.active = true;
            next_instruction_.address = top.instr_addr;
        }

        if (top.data_req) {
            validate_address(top.data_addr, "data");
            next_data_.active = true;
            next_data_.address = top.data_addr;
            next_data_.write_data = top.data_wdata;
            next_data_.write_strobe = top.data_we ? top.data_be : 0;
            next_data_.read_data = top.data_we ? 0 : read_word(top.data_addr);
        }
    }

    void complete_cycle() {
        if (next_data_.active && next_data_.write_strobe != 0) {
            const std::uint32_t aligned = next_data_.address & ~3u;
            for (unsigned lane = 0; lane < 4; ++lane) {
                if ((next_data_.write_strobe >> lane) & 1u) {
                    memory_[aligned + lane] =
                        static_cast<std::uint8_t>(next_data_.write_data >> (lane * 8));
                }
            }
        }
        instruction_response_ = next_instruction_;
        data_response_ = next_data_;
    }

private:
    struct InstructionResponse {
        bool active = false;
        std::uint32_t address = 0;
    };

    struct DataResponse {
        bool active = false;
        std::uint32_t address = 0;
        std::uint32_t write_data = 0;
        std::uint8_t write_strobe = 0;
        std::uint32_t read_data = 0;
    };

    void validate_address(std::uint32_t address, const char* port) const {
        const std::uint32_t aligned = address & ~3u;
        if (aligned > memory_.size() - 4) {
            throw std::runtime_error(std::string("external ") + port +
                                     " request is out of range");
        }
    }

    std::vector<std::uint8_t> memory_;
    InstructionResponse instruction_response_;
    InstructionResponse next_instruction_;
    DataResponse data_response_;
    DataResponse next_data_;
};

FrameArtifact capture_frame(const Config& config, const MemoryBus& memory,
                            std::uint32_t address, std::uint32_t index,
                            Sha256& aggregate_hash) {
    const std::uint64_t pixels = static_cast<std::uint64_t>(config.width) * config.height;
    const std::uint64_t source_bytes = pixels * 4u;
    if ((address & 3u) != 0) throw std::runtime_error("framebuffer address is not word aligned");
    if (source_bytes > kMemoryBytes || address > kMemoryBytes - source_bytes) {
        throw std::runtime_error("framebuffer lies outside external memory");
    }
    std::vector<std::uint8_t> rgb(static_cast<std::size_t>(pixels * 3u));
    for (std::uint64_t pixel = 0; pixel < pixels; ++pixel) {
        const std::uint32_t value = memory.read_word(address + static_cast<std::uint32_t>(pixel * 4u));
        rgb[static_cast<std::size_t>(pixel * 3u)] = static_cast<std::uint8_t>(value >> 16);
        rgb[static_cast<std::size_t>(pixel * 3u + 1)] = static_cast<std::uint8_t>(value >> 8);
        rgb[static_cast<std::size_t>(pixel * 3u + 2)] = static_cast<std::uint8_t>(value);
    }

    std::ostringstream name;
    name << "frame-" << std::setw(6) << std::setfill('0') << index << ".rgb";
    const fs::path output_path = config.frames_dir / name.str();
    reject_protected_path(output_path, "frame output");
    std::ofstream output(output_path, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot create frame: " + output_path.string());
    output.write(reinterpret_cast<const char*>(rgb.data()), static_cast<std::streamsize>(rgb.size()));
    if (!output) throw std::runtime_error("cannot write frame: " + output_path.string());

    hash_u32(aggregate_hash, index);
    aggregate_hash.update(rgb.data(), rgb.size());
    return FrameArtifact{index, output_path, hash_bytes(rgb)};
}

void write_uart_log(const Config& config, const Report& report) {
    reject_protected_path(config.uart_log, "UART output");
    if (!config.uart_log.parent_path().empty()) fs::create_directories(config.uart_log.parent_path());
    std::ofstream output(config.uart_log, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot create UART log: " + config.uart_log.string());
    output.write(report.uart.data(), static_cast<std::streamsize>(report.uart.size()));
    if (!output) throw std::runtime_error("cannot write UART log: " + config.uart_log.string());
}

void write_report(const Config& config, const Report& report) {
    reject_protected_path(config.result_file, "result output");
    if (!config.result_file.parent_path().empty()) fs::create_directories(config.result_file.parent_path());
    std::ofstream output(config.result_file, std::ios::trunc);
    if (!output) throw std::runtime_error("cannot create result: " + config.result_file.string());
    output << "{\n"
           << "  \"schema_version\": 1,\n"
           << "  \"booted\": " << (report.booted ? "true" : "false") << ",\n"
           << "  \"doom_started\": " << (report.doom_started ? "true" : "false") << ",\n"
           << "  \"finished\": " << (report.finished ? "true" : "false") << ",\n"
           << "  \"failed\": " << (report.failed ? "true" : "false") << ",\n"
           << "  \"trap\": " << (report.trapped ? "true" : "false") << ",\n"
           << "  \"success\": " << (report.success ? "true" : "false") << ",\n"
           << "  \"exit_reason\": \"" << json_escape(report.exit_reason) << "\",\n"
           << "  \"error\": " << (report.error.empty() ? "null" : "\"" + json_escape(report.error) + "\"") << ",\n"
           << "  \"cycles\": " << report.cycles << ",\n"
           << "  \"milestone_cycles\": {\n"
           << "    \"boot\": " << report.boot_cycle << ",\n"
           << "    \"doom_started\": " << report.doom_started_cycle << ",\n"
           << "    \"first_capture\": " << report.first_capture_cycle << ",\n"
           << "    \"finish\": " << report.finish_cycle << "\n"
           << "  },\n"
           << "  \"tics\": " << report.stat_game_tics << ",\n"
           << "  \"frames\": " << report.frames.size() << ",\n"
           << "  \"retired_instructions\": " << report.retired_instructions << ",\n"
           << "  \"native_trace_events\": " << report.native_trace_events << ",\n"
           << "  \"cycle_trace_samples\": " << report.cycle_trace_samples << ",\n"
           << "  \"native_trace_hash_samples\": " << report.native_trace_hash_samples << ",\n"
           << "  \"retire_trace_hash_samples\": " << report.retire_trace_hash_samples << ",\n"
           << "  \"input_count\": " << report.input_count << ",\n"
           << "  \"firmware_stats\": {\n"
           << "    \"simulation_frames\": " << report.stat_simulation_frames << ",\n"
           << "    \"game_tics\": " << report.stat_game_tics << ",\n"
           << "    \"captured_frames\": " << report.stat_captured_frames << ",\n"
           << "    \"exit_code\": " << report.stat_exit_code << "\n"
           << "  },\n"
           << "  \"hashes\": {\n"
           << "    \"simulator_sha256\": \"" << report.simulator_sha256 << "\",\n"
           << "    \"rtl_sources_sha256\": \"" << report.rtl_sources_sha256 << "\",\n"
           << "    \"firmware_sha256\": \"" << report.firmware_sha256 << "\",\n"
           << "    \"wad_sha256\": \"" << report.wad_sha256 << "\",\n"
           << "    \"input_text_sha256\": \"" << report.input_text_sha256 << "\",\n"
           << "    \"input_records_sha256\": \"" << report.input_records_sha256 << "\",\n"
           << "    \"cycle_trace_sha256\": \"" << report.cycle_trace_sha256 << "\",\n"
           << "    \"native_trace_sha256\": \"" << report.native_trace_sha256 << "\",\n"
           << "    \"retire_trace_sha256\": \"" << report.retire_trace_sha256 << "\",\n"
           << "    \"frames_sha256\": \"" << report.frames_sha256 << "\",\n"
           << "    \"uart_sha256\": \"" << report.uart_sha256 << "\"\n"
           << "  },\n"
           << "  \"artifacts\": {\n"
           << "    \"uart_log\": \"" << json_escape(absolute_string(config.uart_log)) << "\",\n"
           << "    \"frames\": [\n";
    for (std::size_t i = 0; i < report.frames.size(); ++i) {
        const auto& frame = report.frames[i];
        output << "      {\"index\": " << frame.index << ", \"path\": \""
               << json_escape(absolute_string(frame.path)) << "\", \"sha256\": \""
               << frame.sha256 << "\"}" << (i + 1 == report.frames.size() ? "\n" : ",\n");
    }
    output << "    ]\n"
           << "  },\n"
           << "  \"last_retirement\": ";
    if (report.last_retire_sample) {
        const RetireSample& sample = *report.last_retire_sample;
        output << "{\"cycle\": " << sample.cycle
               << ", \"order\": " << sample.order
               << ", \"pc\": \"" << hex32(sample.pc)
               << "\", \"instruction\": \"" << hex32(sample.instruction)
               << "\", \"next_pc\": \"" << hex32(sample.next_pc)
               << "\", \"trap\": " << (sample.trapped ? "true" : "false") << "},\n";
    } else {
        output << "null,\n";
    }
    output
           << "  \"retire_trace_samples\": [\n";
    for (std::size_t i = 0; i < report.retire_samples.size(); ++i) {
        const RetireSample& sample = report.retire_samples[i];
        output << "    {\"cycle\": " << sample.cycle
               << ", \"order\": " << sample.order
               << ", \"pc\": \"" << hex32(sample.pc)
               << "\", \"instruction\": \"" << hex32(sample.instruction)
               << "\", \"next_pc\": \"" << hex32(sample.next_pc)
               << "\", \"rd\": " << static_cast<unsigned>(sample.register_write_address)
               << ", \"rd_wdata\": \"" << hex32(sample.register_write_data)
               << "\", \"mem_addr\": \"" << hex32(sample.memory_address)
               << "\", \"mem_rmask\": " << static_cast<unsigned>(sample.memory_read_mask)
               << ", \"mem_wmask\": " << static_cast<unsigned>(sample.memory_write_mask)
               << ", \"mem_rdata\": \"" << hex32(sample.memory_read_data)
               << "\", \"mem_wdata\": \"" << hex32(sample.memory_write_data)
               << "\", \"trap\": " << (sample.trapped ? "true" : "false") << "}"
               << (i + 1 == report.retire_samples.size() ? "\n" : ",\n");
    }
    output << "  ],\n"
           << "  \"hardware\": {\n"
           << "    \"kind\": \"cycle-accurate synthesizable RTL simulation\",\n"
           << "    \"soc\": \"aisl_soc_cv\",\n"
           << "    \"cpu\": \"OpenHW Group CV32E40P 360d272898d81806be3377193870dbf83a3ea79f\",\n"
           << "    \"isa\": \"RV32IMC\",\n"
           << "    \"external_memory_bytes\": " << kMemoryBytes << ",\n"
           << "    \"memory_ports\": \"independent instruction/data OBI\",\n"
           << "    \"memory_wait_cycles\": " << config.memory_latency << ",\n"
           << "    \"obi_response_latency_cycles\": 1,\n"
           << "    \"cycle_trace_stride_cycles\": " << config.cycle_trace_stride << ",\n"
           << "    \"execution_trace_stride_events\": " << config.execution_trace_stride << ",\n"
           << "    \"retirement_trace_kind\": \"decode/minstret diagnostic; not formal RVFI\"\n"
           << "  }\n"
           << "}\n";
    if (!output) throw std::runtime_error("cannot write result: " + config.result_file.string());
}

template <std::size_t Size>
void append_u8(std::array<std::uint8_t, Size>& record, std::size_t& offset,
               std::uint8_t value) {
    record[offset++] = value;
}

template <std::size_t Size>
void append_u32(std::array<std::uint8_t, Size>& record, std::size_t& offset,
                std::uint32_t value) {
    for (unsigned byte = 0; byte < 4; ++byte)
        record[offset++] = static_cast<std::uint8_t>(value >> (byte * 8));
}

template <std::size_t Size>
void append_u64(std::array<std::uint8_t, Size>& record, std::size_t& offset,
                std::uint64_t value) {
    for (unsigned byte = 0; byte < 8; ++byte)
        record[offset++] = static_cast<std::uint8_t>(value >> (byte * 8));
}

void hash_cycle(Sha256& hash, const Vaisl_soc& top, std::uint64_t cycle) {
    std::array<std::uint8_t, 64> record{};
    std::size_t offset = 0;
    append_u64(record, offset, cycle);
    append_u8(record, offset, top.instr_req);
    append_u8(record, offset, top.instr_gnt);
    append_u8(record, offset, top.instr_rvalid);
    append_u32(record, offset, top.instr_addr);
    append_u32(record, offset, top.instr_rdata);
    append_u8(record, offset, top.data_req);
    append_u8(record, offset, top.data_gnt);
    append_u8(record, offset, top.data_rvalid);
    append_u8(record, offset, top.data_we);
    append_u8(record, offset, top.data_be);
    append_u32(record, offset, top.data_addr);
    append_u32(record, offset, top.data_wdata);
    append_u32(record, offset, top.data_rdata);
    append_u8(record, offset, top.trap);
    append_u8(record, offset, top.trace_valid);
    append_u64(record, offset, top.trace_data);
    append_u8(record, offset, top.rvfi_valid);
    append_u8(record, offset, top.status_booted);
    append_u8(record, offset, top.status_doom_started);
    append_u8(record, offset, top.status_finished);
    append_u8(record, offset, top.status_failed);
    hash.update(record.data(), offset);
}

void hash_native_trace(Sha256& hash, const Vaisl_soc& top, std::uint64_t cycle) {
    std::array<std::uint8_t, 16> record{};
    std::size_t offset = 0;
    append_u64(record, offset, cycle);
    append_u64(record, offset, top.trace_data);
    hash.update(record.data(), offset);
}

void hash_retirement(Sha256& hash, const Vaisl_soc& top, std::uint64_t cycle) {
    std::array<std::uint8_t, 60> record{};
    std::size_t offset = 0;
    append_u64(record, offset, cycle);
    append_u64(record, offset, top.rvfi_order);
    append_u32(record, offset, top.rvfi_insn);
    append_u8(record, offset, top.rvfi_trap);
    append_u8(record, offset, top.rvfi_halt);
    append_u8(record, offset, top.rvfi_intr);
    append_u32(record, offset, top.rvfi_pc_rdata);
    append_u32(record, offset, top.rvfi_pc_wdata);
    append_u8(record, offset, top.rvfi_rs1_addr);
    append_u8(record, offset, top.rvfi_rs2_addr);
    append_u32(record, offset, top.rvfi_rs1_rdata);
    append_u32(record, offset, top.rvfi_rs2_rdata);
    append_u8(record, offset, top.rvfi_rd_addr);
    append_u32(record, offset, top.rvfi_rd_wdata);
    append_u32(record, offset, top.rvfi_mem_addr);
    append_u8(record, offset, top.rvfi_mem_rmask);
    append_u8(record, offset, top.rvfi_mem_wmask);
    append_u32(record, offset, top.rvfi_mem_rdata);
    append_u32(record, offset, top.rvfi_mem_wdata);
    hash.update(record.data(), offset);
}

RetireSample make_sample(const Vaisl_soc& top, std::uint64_t cycle) {
    return RetireSample{
        cycle, top.rvfi_order, top.rvfi_insn, top.rvfi_pc_rdata, top.rvfi_pc_wdata,
        top.rvfi_mem_addr, top.rvfi_mem_rdata, top.rvfi_mem_wdata, top.rvfi_rd_wdata,
        static_cast<std::uint8_t>(top.rvfi_mem_rmask),
        static_cast<std::uint8_t>(top.rvfi_mem_wmask),
        static_cast<std::uint8_t>(top.rvfi_rd_addr), static_cast<bool>(top.rvfi_trap),
    };
}

Report simulate(const Config& config) {
    Report report;
    const std::vector<std::uint8_t> firmware = read_file(config.firmware, "firmware");
    const std::vector<std::uint8_t> wad = read_file(config.wad, "WAD");
    const std::vector<std::uint8_t> input_text = read_file(config.inputs, "input schedule");
    if (firmware.empty()) throw std::runtime_error("firmware image is empty");
    if (firmware.size() > kWadAddress) throw std::runtime_error("firmware overlaps WAD region");
    if (wad.size() > kInputAddress - kWadAddress) throw std::runtime_error("WAD overlaps input region");
    const std::vector<InputEvent> events = parse_events(input_text);
    if (events.size() > std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error("too many input records");
    }
    const std::vector<std::uint8_t> input_records = encode_events(events);
    if (input_records.size() > kMemoryBytes - kInputAddress) {
        throw std::runtime_error("input records do not fit in external memory");
    }

    report.firmware_sha256 = hash_bytes(firmware);
    report.wad_sha256 = hash_bytes(wad);
    report.input_text_sha256 = hash_bytes(input_text);
    report.input_records_sha256 = hash_bytes(input_records);
    report.input_count = static_cast<std::uint32_t>(events.size());
    report.firmware_wad_size = static_cast<std::uint32_t>(wad.size());

    MemoryBus memory(config.memory_latency);
    memory.load(0, firmware, "firmware");
    memory.load(kWadAddress, wad, "WAD");
    memory.load(kInputAddress, input_records, "input records");

    reject_protected_path(config.frames_dir, "frame output directory");
    fs::create_directories(config.frames_dir);
    std::vector<bool> frame_seen(config.frame_count, false);

    Verilated::randReset(0);
    auto top = std::make_unique<Vaisl_soc>();
    top->clk = 0;
    top->resetn = 0;
    top->instr_gnt = 1;
    top->instr_rvalid = 0;
    top->instr_rdata = 0;
    top->data_gnt = 1;
    top->data_rvalid = 0;
    top->data_rdata = 0;
    top->cfg_frame_count = config.frame_count;
    top->cfg_frame_warmup = config.frame_warmup;
    top->cfg_input_count = report.input_count;
    top->cfg_wad_size = report.firmware_wad_size;
    top->cfg_skill = config.skill;
    top->cfg_episode = config.episode;
    top->cfg_map = config.map;
    top->eval();

    for (std::uint32_t cycle = 0; cycle < config.reset_cycles; ++cycle) {
        top->clk = 0;
        memory.drive_responses(*top);
        top->eval();
        memory.capture_requests(*top);
        top->clk = 1;
        top->eval();
        memory.complete_cycle();
    }
    top->resetn = 1;

    Sha256 cycle_hash;
    Sha256 native_trace_hash;
    Sha256 retire_trace_hash;
    Sha256 frame_hash;
    bool announced_boot = false;
    bool announced_doom = false;
    std::uint64_t next_cycle_trace = 1;
    std::uint32_t native_trace_countdown = 0;
    std::uint32_t retire_trace_countdown = 0;

    try {
        while (report.cycles < config.max_cycles) {
            top->clk = 0;
            memory.drive_responses(*top);
            top->eval();
            memory.capture_requests(*top);
            top->clk = 1;
            top->eval();
            ++report.cycles;
            memory.complete_cycle();

            const bool periodic_cycle_trace = report.cycles == next_cycle_trace;
            if (periodic_cycle_trace)
                next_cycle_trace += config.cycle_trace_stride;
            if (periodic_cycle_trace || top->event_valid || top->trap) {
                hash_cycle(cycle_hash, *top, report.cycles);
                ++report.cycle_trace_samples;
            }
            if (top->trace_valid) {
                ++report.native_trace_events;
                if (native_trace_countdown == 0) {
                    hash_native_trace(native_trace_hash, *top, report.cycles);
                    ++report.native_trace_hash_samples;
                    native_trace_countdown = config.execution_trace_stride - 1;
                } else {
                    --native_trace_countdown;
                }
            }
            if (top->rvfi_valid) {
                ++report.retired_instructions;
                if (retire_trace_countdown == 0) {
                    hash_retirement(retire_trace_hash, *top, report.cycles);
                    ++report.retire_trace_hash_samples;
                    retire_trace_countdown = config.execution_trace_stride - 1;
                } else {
                    --retire_trace_countdown;
                }
                report.last_retire_sample = make_sample(*top, report.cycles);
                if (report.retire_samples.size() < config.trace_sample_limit) {
                    report.retire_samples.push_back(*report.last_retire_sample);
                }
            }
            if (top->uart_tx_valid) {
                report.uart.push_back(static_cast<char>(top->uart_tx_data));
            }
            if (top->status_booted && !announced_boot) {
                announced_boot = true;
                report.boot_cycle = report.cycles;
                std::cout << "AISL_BOOTED\n";
            }
            if (top->status_doom_started && !announced_doom) {
                announced_doom = true;
                report.doom_started_cycle = report.cycles;
                std::cout << "AISL_DOOM_STARTED\n";
            }
            if (top->frame_capture_valid) {
                const std::uint32_t index = top->frame_index;
                if (index >= config.frame_count) {
                    throw std::runtime_error("firmware requested out-of-range frame index " + std::to_string(index));
                }
                if (frame_seen[index]) {
                    throw std::runtime_error("firmware requested duplicate frame index " + std::to_string(index));
                }
                if (index != report.frames.size()) {
                    throw std::runtime_error("firmware requested non-sequential frame index " + std::to_string(index));
                }
                frame_seen[index] = true;
                report.frames.push_back(capture_frame(config, memory, top->frame_address, index, frame_hash));
                if (report.first_capture_cycle == 0) report.first_capture_cycle = report.cycles;
            }

            if (top->trap) {
                report.trapped = true;
                report.exit_reason = "trap";
                break;
            }
            if (top->status_failed) {
                report.failed = true;
                report.exit_reason = "firmware_failed";
                break;
            }
            if (top->status_finished) {
                report.finished = true;
                report.finish_cycle = report.cycles;
                report.exit_reason = "finished";
                std::cout << "AISL_FINISHED\n";
                break;
            }
        }
        if (report.exit_reason == "not_started") report.exit_reason = "timeout";
    } catch (const std::exception& exception) {
        report.exit_reason = "simulation_error";
        report.error = exception.what();
    }

    report.booted = top->status_booted;
    report.doom_started = top->status_doom_started;
    report.finished = report.finished || static_cast<bool>(top->status_finished);
    report.failed = report.failed || static_cast<bool>(top->status_failed);
    report.trapped = report.trapped || static_cast<bool>(top->trap);
    report.stat_simulation_frames = top->stat_simulation_frames;
    report.stat_game_tics = top->stat_game_tics;
    report.stat_captured_frames = top->stat_captured_frames;
    report.stat_exit_code = top->stat_exit_code;
    report.cycle_trace_sha256 = cycle_hash.hex_digest();
    report.native_trace_sha256 = native_trace_hash.hex_digest();
    report.retire_trace_sha256 = retire_trace_hash.hex_digest();
    report.frames_sha256 = frame_hash.hex_digest();
    Sha256 uart_hash;
    uart_hash.update(report.uart);
    report.uart_sha256 = uart_hash.hex_digest();

    report.success = report.exit_reason == "finished" && report.booted && report.doom_started &&
                     !report.failed && !report.trapped && report.error.empty() &&
                     report.frames.size() == config.frame_count && report.stat_exit_code == 0;
    if (!report.success && report.error.empty()) {
        if (report.exit_reason == "timeout") {
            report.error = "maximum cycle count reached before finish";
        } else if (report.exit_reason == "trap") {
            report.error = "CPU trap asserted";
        } else if (report.exit_reason == "firmware_failed") {
            report.error = "firmware issued fail control event";
        } else if (report.finished && !report.booted) {
            report.error = "firmware finished without boot marker";
        } else if (report.finished && !report.doom_started) {
            report.error = "firmware finished without Doom-start marker";
        } else if (report.frames.size() != config.frame_count) {
            report.error = "firmware finished with incorrect captured frame count";
        } else if (report.stat_exit_code != 0) {
            report.error = "firmware reported non-zero exit code";
        }
    }
    top->final();
    return report;
}

} // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Config config;
    try {
        config = parse_arguments(argc, argv);
        Report report = simulate(config);
        report.simulator_sha256 = hash_bytes(read_file(fs::absolute(argv[0]), "simulator executable"));
        write_uart_log(config, report);
        write_report(config, report);
        if (!report.success) {
            std::cerr << "simulation failed: " << report.exit_reason;
            if (!report.error.empty()) std::cerr << ": " << report.error;
            std::cerr << '\n';
        }
        return report.success ? 0 : 1;
    } catch (const std::exception& exception) {
        std::cerr << "simulator error: " << exception.what() << '\n';
        return 2;
    }
}
