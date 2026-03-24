#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

struct Profile {
    std::string video_codec = "libx265";
    int crf = 22;
    std::string preset = "medium";
    std::string audio_codec = "aac";
    std::string audio_bitrate = "192k";
    std::string container = "mkv";
};

struct Options {
    std::string input;
    std::string host;
    std::string user;
    int port = 22;
    std::string profile_path;
    std::string remote_base = "~/mkv_jobs";
    std::string output_dir = "./out";
    bool dry_run = false;
};

static std::string read_file(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("Cannot open file: " + path);
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

static std::optional<std::string> json_string(const std::string& text, const std::string& key) {
    std::regex r("\"" + key + "\"\\s*:\\s*\"([^\"]+)\"");
    std::smatch m;
    if (std::regex_search(text, m, r)) return m[1].str();
    return std::nullopt;
}

static std::optional<int> json_int(const std::string& text, const std::string& key) {
    std::regex r("\"" + key + "\"\\s*:\\s*([0-9]+)");
    std::smatch m;
    if (std::regex_search(text, m, r)) return std::stoi(m[1].str());
    return std::nullopt;
}

static Profile load_profile(const std::string& path) {
    const std::string raw = read_file(path);
    Profile p;
    if (auto v = json_string(raw, "video_codec")) p.video_codec = *v;
    if (auto v = json_int(raw, "crf")) p.crf = *v;
    if (auto v = json_string(raw, "preset")) p.preset = *v;
    if (auto v = json_string(raw, "audio_codec")) p.audio_codec = *v;
    if (auto v = json_string(raw, "audio_bitrate")) p.audio_bitrate = *v;
    if (auto v = json_string(raw, "container")) p.container = *v;
    return p;
}

static std::string shell_quote(const std::string& x) {
    std::string out = "'";
    for (char c : x) {
        if (c == '\'') out += "'\\''";
        else out += c;
    }
    out += "'";
    return out;
}

static int run_cmd(const std::string& cmd, bool dry_run) {
    std::cout << "$ " << cmd << "\n";
    if (dry_run) return 0;
    return std::system(cmd.c_str());
}

static std::string utc_job_id() {
    auto now = std::chrono::system_clock::now();
    std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::tm* gmt = std::gmtime(&t);
    std::ostringstream os;
    os << "job_" << std::put_time(gmt, "%Y%m%dT%H%M%SZ");
    return os.str();
}

static void usage() {
    std::cout
        << "Usage: client_beta1_cpp <input.mkv> --host <host> --user <user> --profile <file.json> [options]\n"
        << "Options:\n"
        << "  --port <int>          SSH port (default: 22)\n"
        << "  --remote-base <dir>   Remote base dir (default: ~/mkv_jobs)\n"
        << "  --output-dir <dir>    Local output dir (default: ./out)\n"
        << "  --dry-run             Print commands only\n";
}

static Options parse_args(int argc, char** argv) {
    if (argc < 2) {
        usage();
        throw std::runtime_error("missing arguments");
    }

    Options o;
    o.input = argv[1];
    for (int i = 2; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&](const std::string& name) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("missing value for " + name);
            return argv[++i];
        };

        if (a == "--host") o.host = next(a);
        else if (a == "--user") o.user = next(a);
        else if (a == "--port") o.port = std::stoi(next(a));
        else if (a == "--profile") o.profile_path = next(a);
        else if (a == "--remote-base") o.remote_base = next(a);
        else if (a == "--output-dir") o.output_dir = next(a);
        else if (a == "--dry-run") o.dry_run = true;
        else throw std::runtime_error("unknown argument: " + a);
    }

    if (o.host.empty() || o.user.empty() || o.profile_path.empty()) {
        usage();
        throw std::runtime_error("required: --host --user --profile");
    }
    return o;
}

int main(int argc, char** argv) {
    try {
        Options opt = parse_args(argc, argv);

        std::filesystem::path in(opt.input);
        if (!std::filesystem::exists(in)) throw std::runtime_error("Input not found: " + opt.input);
        if (in.extension() != ".mkv") throw std::runtime_error("Input must be .mkv");
        if (!std::filesystem::exists(opt.profile_path)) throw std::runtime_error("Profile not found: " + opt.profile_path);

        Profile p = load_profile(opt.profile_path);
        std::filesystem::create_directories(opt.output_dir);

        const std::string job = utc_job_id();
        const std::string remote_dir = opt.remote_base + "/" + job;
        const std::string remote_input = remote_dir + "/" + in.filename().string();
        const std::string output_name = in.stem().string() + ".cppbeta1." + p.container;
        const std::string remote_output = remote_dir + "/" + output_name;
        const std::string local_output = (std::filesystem::path(opt.output_dir) / output_name).string();

        const std::string login = opt.user + "@" + opt.host;
        const std::string ssh_mkdir = "ssh -p " + std::to_string(opt.port) + " " + shell_quote(login) + " mkdir -p " + shell_quote(remote_dir);
        const std::string scp_upload = "scp -P " + std::to_string(opt.port) + " " + shell_quote(opt.input) + " " + shell_quote(login + ":" + remote_input);

        std::ostringstream ff;
        ff << "ffmpeg -y -threads 0 -i " << shell_quote(remote_input)
           << " -map 0 -c:v " << shell_quote(p.video_codec)
           << " -preset " << shell_quote(p.preset)
           << " -crf " << p.crf
           << " -c:a " << shell_quote(p.audio_codec)
           << " -b:a " << shell_quote(p.audio_bitrate)
           << " " << shell_quote(remote_output);

        const std::string ssh_ffmpeg = "ssh -p " + std::to_string(opt.port) + " " + shell_quote(login) + " " + ff.str();
        const std::string scp_download = "scp -P " + std::to_string(opt.port) + " " + shell_quote(login + ":" + remote_output) + " " + shell_quote(local_output);

        if (run_cmd(ssh_mkdir, opt.dry_run) != 0) throw std::runtime_error("mkdir command failed");
        if (run_cmd(scp_upload, opt.dry_run) != 0) throw std::runtime_error("upload failed");
        if (run_cmd(ssh_ffmpeg, opt.dry_run) != 0) throw std::runtime_error("ffmpeg failed");
        if (run_cmd(scp_download, opt.dry_run) != 0) throw std::runtime_error("download failed");

        std::cout << "Done: " << local_output << "\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "Error: " << ex.what() << "\n";
        return 1;
    }
}
