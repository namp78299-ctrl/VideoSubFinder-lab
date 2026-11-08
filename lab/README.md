# VSF 6.10 lab

Nhánh thử: lab/vsf610-profile. Không đổi thuật toán hoặc binary của DuanLayLink.

Workflow VSF 6.10 — source review chỉ có workflow_dispatch. Nó kiểm tra105 file source và khả năng áp patch, rồi báo dependency còn thiếu. Không compile, không chạy benchmark, không upload artifact. PASS của workflow chỉ là source/patch gate; build_ready luôn false cho tới khi có bước xác minh build thực tế.

Hai workflow đồng bộ kế thừa được đổi đuôi thành .yml.disabled trên nhánh này vì vẫn trỏ tới repo/tài khoản của tác giả gốc. Không sửa main.

## Việc tiếp theo

1. Review lab/BUILD_HANDOFF.md và Docs/build.txt.
2. Resolve lab/deps_lock.json: URL/hash archive bất biến, exact compiler/SDK/CUDA và paths. Không chạy installer hoặc lấy latest trong source-review job.
3. Thêm hai job build riêng trên cùng môi trường, Release/x64, source baseline và instrumented riêng. Chưa có build job trong workflow hiện tại.
4. Kiểm tra output parity trên video thật và GTX1050Ti; đo overhead instrumentation; rồi mới thử tối ưu và đo tốc độ.

Nếu workflow không xuất hiện ở tab Actions vì chỉ có trên nhánh thử, chưa merge nó vào main chỉ để chạy. Người duy trì sẽ chọn cách dispatch/đưa workflow lên default branch sau khi review và chốt dependency.

Gói review/patch không chứa .env, token, video hoặc runtime DLL của người dùng.

## Experimental recipe added

Pinned downloads and the alternative FFmpeg SDK strategy are documented in BUILD_RECIPE_REVIEW.md. scripts/prepare_vsf_toolchain.ps1 and scripts/build_vsf_pair.ps1 are runner-only. .github/workflows/vsf610-build-pair.yml is a manual-only experimental build recipe. No build or performance result has been claimed.
