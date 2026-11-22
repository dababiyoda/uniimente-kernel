// Stream paired input and expected results from the unmodified upstream VM.
// Build with the pinned CuBFF checkout on the include path.
#ifdef CUBFF_HEADLESS
#include "bff_noheads.cu"
#else
#include "bff.cu"
#endif

#include <array>

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  uint64_t cases = std::stoull(argv[1]);
  constexpr size_t width = 2 * kSingleTapeSize;
  static_assert(width == 128);
  constexpr std::array<uint16_t, 6> caps = {0, 1, 16, 128, 512, 8192};
  constexpr std::array<uint8_t, 16> rich = {
      '+', '-', '>', '<', '{', '}', '.', ',', '[', ']', 0, 0, 0, 'x', 'y', 'z',
  };
  constexpr uint64_t seed = 20261122;
  for (uint64_t i = 0; i < cases; ++i) {
    std::array<uint8_t, width> tape{};
    for (size_t first = 0; first < width; first += 8) {
      uint64_t bits = SplitMix64(seed + i * (width / 8) + first / 8);
      for (size_t j = 0; j < 8; ++j, bits >>= 8) {
        uint8_t byte = bits & 255;
        tape[first + j] = (i % 8 == 0) ? rich[byte & 15] : byte;
      }
    }
    auto output = tape;
    uint16_t cap = caps[(i / 8) % caps.size()];
    uint16_t active = Bff::Evaluate(output.data(), cap, false);
    std::array<uint8_t, 4> counts = {
        uint8_t(cap), uint8_t(cap >> 8), uint8_t(active), uint8_t(active >> 8),
    };
    if (fwrite(tape.data(), 1, tape.size(), stdout) != tape.size() ||
        fwrite(output.data(), 1, output.size(), stdout) != output.size() ||
        fwrite(counts.data(), 1, counts.size(), stdout) != counts.size()) {
      return 1;
    }
  }
  return fflush(stdout) == 0 ? 0 : 1;
}
