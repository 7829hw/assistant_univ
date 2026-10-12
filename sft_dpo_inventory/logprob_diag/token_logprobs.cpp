// 결정 75: 고정 token id열의 응답 token마다 log 확률(온도 1, 원래 분포)과 top-K를 llama.cpp(b11434, CUDA)로 계산한다.
// 생성하지 않는다. Ollama 서버가 아니라 llama.cpp 라이브러리를 직접 부른다.
//
//   token_logprobs MODEL.gguf IN.txt OUT.bin [K=64] [N_CTX=16384]
//
// IN.txt 한 줄 = "seq_index resp_start n tok_0 ... tok_{n-1}". 위치 t(resp_start ≤ t < n)의 token을 위치 t-1의 logits로 채점한다.
// OUT.bin 열마다: int32 seq_index, int32 count, 그다음 count개의 레코드
//   {float target_lp, int32 top1, int32 ids[K], float lps[K]}(top-K는 log 확률 내림차순).
#include "llama.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

int main(int argc, char ** argv) {
    if (argc < 4) { fprintf(stderr, "usage: %s MODEL IN OUT [K] [N_CTX]\n", argv[0]); return 2; }
    const int K = argc > 4 ? atoi(argv[4]) : 64;
    const int N_CTX = argc > 5 ? atoi(argv[5]) : 16384;
    llama_backend_init();
    auto mp = llama_model_default_params();
    mp.n_gpu_layers = -1;
    llama_model * model = llama_model_load_from_file(argv[1], mp);
    if (!model) { fprintf(stderr, "load failed\n"); return 1; }
    auto cp = llama_context_default_params();
    cp.n_ctx = N_CTX; cp.n_batch = 2048; cp.n_ubatch = 2048; cp.n_seq_max = 1; cp.no_perf = true;
    llama_context * ctx = llama_init_from_model(model, cp);
    if (!ctx) { fprintf(stderr, "context failed\n"); return 1; }
    const int n_vocab = llama_vocab_n_tokens(llama_model_get_vocab(model));
    fprintf(stderr, "n_vocab %d flash_attn %s n_ctx %u\n", n_vocab, llama_flash_attn_type_name(cp.flash_attn_type), llama_n_ctx(ctx));

    std::ifstream in(argv[2]);
    FILE * out = fopen(argv[3], "wb");
    std::string line;
    std::vector<int> idx(n_vocab);
    std::vector<double> lp(n_vocab);
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::istringstream ss(line);
        int seq, start, n; ss >> seq >> start >> n;
        std::vector<llama_token> toks(n);
        for (int i = 0; i < n; i++) ss >> toks[i];
        if (n > N_CTX || start < 1 || start >= n) { fprintf(stderr, "bad seq %d n=%d start=%d\n", seq, n, start); return 1; }
        llama_memory_clear(llama_get_memory(ctx), true);
        int count = n - start;
        fwrite(&seq, 4, 1, out); fwrite(&count, 4, 1, out);
        llama_batch batch = llama_batch_init(2048, 0, 1);
        for (int b0 = 0; b0 < n - 1; b0 += 2048) {     // 마지막 token은 입력하지 않는다(다음 token을 채점할 필요 없음)
            int b1 = std::min(n - 1, b0 + 2048);
            batch.n_tokens = 0;
            for (int p = b0; p < b1; p++) {
                int j = batch.n_tokens++;
                batch.token[j] = toks[p]; batch.pos[j] = p; batch.n_seq_id[j] = 1; batch.seq_id[j][0] = 0;
                batch.logits[j] = p >= start - 1;
            }
            if (llama_decode(ctx, batch) != 0) { fprintf(stderr, "decode failed seq %d\n", seq); return 1; }
            for (int p = std::max(b0, start - 1); p < b1; p++) {
                const float * lg = llama_get_logits_ith(ctx, p - b0);
                double mx = -INFINITY;
                for (int v = 0; v < n_vocab; v++) mx = std::max(mx, (double) lg[v]);
                double s = 0;
                for (int v = 0; v < n_vocab; v++) s += std::exp((double) lg[v] - mx);
                double lse = mx + std::log(s);
                for (int v = 0; v < n_vocab; v++) { lp[v] = (double) lg[v] - lse; idx[v] = v; }
                std::partial_sort(idx.begin(), idx.begin() + K, idx.end(), [&](int a, int b) { return lp[a] > lp[b]; });
                float target = (float) lp[toks[p + 1]];
                int top1 = idx[0];
                fwrite(&target, 4, 1, out); fwrite(&top1, 4, 1, out);
                for (int k = 0; k < K; k++) fwrite(&idx[k], 4, 1, out);
                for (int k = 0; k < K; k++) { float f = (float) lp[idx[k]]; fwrite(&f, 4, 1, out); }
            }
        }
        llama_batch_free(batch);
        fprintf(stderr, "seq %d n %d scored %d\n", seq, n, count);
    }
    fclose(out);
    llama_free(ctx); llama_model_free(model);
    return 0;
}
