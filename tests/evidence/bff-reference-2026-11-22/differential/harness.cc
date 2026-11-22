// Differential-test harness: compiles CuBFF's own bff_noheads code (commit f212e849) unchanged.
// stdin lines: "E <hex128>" -> "<final hex128> <ops>"   (Bff::Evaluate, 8192 steps)
//              "S <hex64> <seed> <epoch>" -> "<score>" (Simulation<Bff>::EvalParsedSelfrep)
#include "bff_noheads.cu"
#include <iostream>
#include <string>
static std::vector<uint8_t> unhex(const std::string &h) {
  std::vector<uint8_t> v;
  for (size_t i = 0; i + 1 < h.size(); i += 2) v.push_back(std::stoi(h.substr(i, 2), nullptr, 16));
  return v;
}
int main() {
  std::string kind;
  Simulation<Bff> sim;
  while (std::cin >> kind) {
    std::string h; std::cin >> h; auto v = unhex(h);
    if (kind == "E") {
      uint8_t tape[128]; memcpy(tape, v.data(), 128);
      size_t ops = Bff::Evaluate(tape, 8 * 1024, false);
      for (int i = 0; i < 128; i++) printf("%02x", tape[i]);
      printf(" %zu\n", ops);
    } else {
      size_t seed, epoch; std::cin >> seed >> epoch;
      printf("%zu\n", sim.EvalParsedSelfrep(v, epoch, seed, false));
    }
  }
}
