# VSF6.10: bàn giao build trên GitHub — bản2

User chọn dùng GitHub, đang chờ URL fork. Chưa tạo hoặc trigger workflow, chưa publish artifact từ xa. Gói ZIP local phục vụ review.

## Đã chốt từ upstream

Kho https://git.code.sf.net/p/videosubfinder/src ; tag VideoSubFinder_6.10 ; commit c3d19abbb4080bb378090d676746751b199b46b1. Toàn bộ105 file tracked có trong source/ của gói này, bao gồm .cu, GUI .cpp/.h/.rc/.ico, thư mục Data/Settings và Docs/build.txt; patch instrumentation nằm riêng.

Đọc Docs/build.txt mục1 trước khi viết recipe. Hướng dẫn upstream nêu MSVC VisualStudioProfessional2022v17.4.4, wxWidgets3.2.1 build wx_vc17.sln, CUDA12.0Update1, OpenCV4.7.0 world build và INSTALL bằng CMake3.25.2. FFmpeg là BtbN shared n5.1 autobuild2023-01-24, archive cũ chưa pin được URL/hash. Không coi URL latest hiện tại là cùng artifact.

Root CMake với IntelDPCPP là đường khác, không phải yêu cầu của đường MSBuild được upstream mô tả. Source C++/CUDA đã rà không có sycl/oneapi/dpcpp. VTune chỉ có hook CUSTOM_TA đang tắt. Không cần chuyển sang compiler Intel cho thử nghiệm MSBuild này.

## Cấu hình build

Dùng solution Interfaces/VideoSubFinderWXW/VideoSubFinderWXW.sln; Release|x64, không dùng ReleaseWithDebugInfo để benchmark vì nhiều project tắt optimization. Giữ hai cây baseline/instrumented riêng vì hardcoded output paths. Chỉ áp native_stage_profile.patch vào instrumented. Mọi dependency/compiler/flags phải giống nhau. Kiểm tra log thực tế /O2,/MD,/std:c++17,/EHsc và nvcc -arch=all. Mặc định Release của project chính cần xác minh flags thực tế thay vì suy ra từ tên cấu hình.

Command cần chạy trong môi trường compiler đã được thiết lập và lockfile dependencies đã giải quyết, không phải lệnh dùng ngay trên máy hiện tại:

msbuild Interfaces\VideoSubFinderWXW\VideoSubFinderWXW.sln -p:Configuration=Release -p:Platform=x64 -v:n -bl:build.binlog

Expected EXE: Build/Release_x64/VideoSubFinderWXW.exe. Không override OutDir để ép dùng chung cây. Cấu hình baseline giữ nguyên không thêm PDB/compiler flags riêng cho một bên; nếu muốn symbols thì tạo cặp build riêng đồng nhất và không dùng chúng thay baseline hiệu năng mà chưa đánh giá.

## Dependency lock còn thiếu

Đã có tên/version upstream; CHƯA có archive hashes/URL bất biến đầy đủ, actual MSVC/SDK patch versions và toàn bộ options của dependencybuild. Điền deps_lock.template.json trước khi chạy. Hash tải về tự tính là hash ghi nhận của file tải, không tự nhận là upstream-authenticated hash. Nếu không lấy được FFmpeg historical binary, một dependency rebuild là baseline mới cần kiểm chứng, không gọi là bản tái lập release gốc.

## Chuẩn bị workflow khi có URL fork

- Xác minh quyền repo, branch và remote của user; không đẩy vào dự án production.
- Draft workflow chỉ manual dispatch, không tự chạy khi push/PR và không dùng pull_request_target. Chốt runner/toolchain/image và artifact upload behavior khi review repo cụ thể.
- Hai source trees sạch từ cùng commit; dependency cache khóa theo lockfile hash, không lấy latest.
- Giữ log/hash/commandline. CI build không có GTX1050Ti thì không báo CUDA runtime/Pascal test đạt; artifact phải kiểm tra trên máy mục tiêu.
- Baseline parity với EXE cũ: ảnh RGB/ILA/ISA và timestamp, rồi instrumented bật/tắt, kiểm tra overhead. Profile inclusive elapsed lồng nhau/song song, không cộng thành walltime.
- Instrumentation counters chưa compile. dump qua appdestructor cần xác minh; kill có thể không dump.

## Điều chỉnh sau review

CodeGeneration XML rỗng đã được lọc; AdditionalOptions -arch=all được ghi riêng. decode_step bao demux và decode_frame; decode_frame bao frame-copy nhưng không bao demux. PE timestamp/noBrepro khiến bit-identical chưa được đảm bảo; không kết luận hash không bao giờ có thể khớp. Bản gói trước thiếu Docs/build.txt và source của app entry point; bản2 bổ sung đầy đủ.

## Đích tối ưu, chưa áp dụng

Giữ full logical geometry, chỉ worker-local context/buffer và chuyển màu padded YUV row views khi path được hỗ trợ; không crop proxy hoặc đổi ngưỡng. DLL microbenchmark tích cực chưa chứng minh nativegain. Đợi stage profile rồi mới quyết định viết bản sửa thuật toán.
