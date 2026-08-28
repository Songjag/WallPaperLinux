# HyprWall

Ứng dụng Python dành riêng cho **Hyprland** để quản lý wallpaper qua `mpvpaper`,
 với giao diện **CustomTkinter** có thể đổi giữa Tiếng Việt và English.

## Cấu trúc mã nguồn

- `main.py`: file khởi chạy ứng dụng.
- `src/app.py`: giao diện CustomTkinter.
- `src/dependencies.py`: kiểm tra/cài dependency.
- `src/wallpaper.py`: tích hợp Hyprland và mpvpaper.
- `src/i18n.py`: tải và áp dụng bản dịch.
- `data/languages.json`: nội dung giao diện Tiếng Việt/English để cập nhật.
- `data/icon.ico`: icon cửa sổ ứng dụng.

Bạn có thể sửa text trong `data/languages.json`. Giữ nguyên các key và
placeholder như `{path}`, `{items}`, `{distro}`, `{package}` để app hiển thị
đúng thông tin động.

## Chức năng

- Tạo tự động thư mục `~/Pictures/HyprlandWallpaper`.
- Đặt ảnh hoặc video làm wallpaper cho toàn bộ màn hình Hyprland.
- Tải video từ URL vào thư viện bằng `yt-dlp`.
- Khi cần, tự cài `customtkinter`, `mpvpaper`, `mpv`, `ffmpeg` và Python package `yt-dlp`.
- Chuyển tức thì toàn bộ giao diện giữa **Tiếng Việt** và **English** từ menu bên trái.
- Cập nhật block riêng trong `~/.config/hypr/hyprland.conf`; file cấu hình cũ
  được backup thành `hyprland.conf.desktop-live-linux.bak`.

## Chạy

```bash
cd DesktopLiveLinux
python3 main.py
```

Hoặc cài sẵn Python dependency:

```bash
python3 -m pip install --user -r requirements.txt
```

## Build executable

```bash
./build.sh
```

Lệnh build tạo executable tại `dist/HyprWall` và nhúng thư mục `data`
(bao gồm `icon.ico` và `languages.json`) vào bundle.

Nhấn **Tự cài dependency** ở lần chạy đầu, hoặc chọn/tải một wallpaper: app sẽ
tự kiểm tra và cài dependency. Với package hệ thống, Polkit (`pkexec`) hoặc
`sudo` sẽ hiện yêu cầu xác thực khi cần.

`CustomTkinter` được tự cài ngay ở lần khởi động đầu tiên; app tự khởi động lại
sau khi cài xong để mở giao diện hiện đại.

Hỗ trợ tự cài theo package manager: `apt`, `dnf`, `pacman`, `zypper`, `apk`,
`xbps-install`, `eopkg` và `nix`. Kho package của từng distro có thể không có
`mpvpaper`; khi đó app giữ nguyên lỗi từ package manager để bạn biết cần bật
repository phù hợp.

## Lưu ý

- App chỉ đặt wallpaper khi được chạy trong phiên **Hyprland**.
- Khi thay wallpaper, app dừng tiến trình `mpvpaper` đang chạy để thay bằng
  wallpaper mới.

- Link tải Song recommended là : các file gif hạn chế tải từ tiktok.