"""
==========================================================
  Telegram Chatbot đơn giản - Dành cho người mới bắt đầu
  Thư viện sử dụng: pyTelegramBotAPI (telebot)
==========================================================
"""
import os
import telebot  # Thư viện chính để giao tiếp với Telegram API

# ============================================================
#  CẤU HÌNH - Thay YOUR_BOT_TOKEN_HERE bằng token thật của bạn
#  Ví dụ: "123456789:ABCdefGhIJKlmNoPQRstuVWXyz"
# ============================================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Khởi tạo đối tượng bot với token đã cung cấp
bot = telebot.TeleBot(BOT_TOKEN)


# ============================================================
#  LỆNH /start
#  Decorator @bot.message_handler() giúp đăng ký hàm này
#  để xử lý khi người dùng gõ lệnh /start
# ============================================================
@bot.message_handler(commands=["start"])
def handle_start(message):
    # message.from_user.first_name lấy tên của người dùng
    ten_nguoi_dung = message.from_user.first_name

    # Chuỗi chào mừng sử dụng f-string để chèn tên người dùng
    chao_mung = (
        f"👋 Xin chào, {ten_nguoi_dung}! Tôi rất vui được gặp bạn!\n\n"
        "🤖 Tôi là chatbot đơn giản được tạo bằng Python.\n\n"
        "Gõ /help để xem danh sách các lệnh tôi hỗ trợ nhé! 😊"
    )

    # Gửi tin nhắn phản hồi về đúng cuộc hội thoại của người dùng
    bot.reply_to(message, chao_mung)


# ============================================================
#  LỆNH /help
#  Xử lý khi người dùng hỏi về các tính năng của bot
# ============================================================
@bot.message_handler(commands=["help"])
def handle_help(message):
    # Danh sách hướng dẫn, dùng ký tự đặc biệt để trình bày đẹp hơn
    huong_dan = (
        "📋 *Danh sách lệnh hỗ trợ:*\n\n"
        "▶ /start — Khởi động bot và nhận lời chào\n"
        "▶ /help  — Xem danh sách lệnh này\n\n"
        "💬 *Tính năng Echo:*\n"
        "Bạn soạn bất kỳ tin nhắn văn bản nào và gửi đi,\n"
        "tôi sẽ nhái lại y chang tin nhắn đó cho bạn! 😄\n\n"
        "---\n"
        "_Được tạo bằng Python & pyTelegramBotAPI_"
    )

    # parse_mode='Markdown' cho phép dùng *in đậm*, _in nghiêng_ trong tin nhắn
    bot.reply_to(message, huong_dan, parse_mode="Markdown")


# ============================================================
#  TÍNH NĂNG ECHO — Nhái lại tin nhắn văn bản
#  content_types=["text"] chỉ kích hoạt với tin nhắn dạng văn bản
#  func=lambda m: not m.text.startswith("/") đảm bảo chỉ nhái
#  những tin nhắn KHÔNG phải lệnh (không bắt đầu bằng dấu /)
# ============================================================
@bot.message_handler(
    content_types=["text"],
    func=lambda m: not m.text.startswith("/")
)
def handle_echo(message):
    # message.text chứa nội dung tin nhắn người dùng vừa gửi
    noi_dung_goc = message.text

    # Thêm tiền tố để bot không nhái y chang mà có chút duyên
    phan_hoi = f"🔁 Bạn vừa nói: \"{noi_dung_goc}\""

    # Trả lời lại người dùng với nội dung đã được định dạng
    bot.reply_to(message, phan_hoi)


# ============================================================
#  VÒNG LẶP CHÍNH — Giữ bot hoạt động liên tục
#  polling(): Bot liên tục hỏi server Telegram "có tin nhắn mới không?"
#  none_stop=True: Tự động khởi động lại nếu có lỗi kết nối
#  interval=0: Kiểm tra ngay lập tức, không chờ
# ============================================================
if __name__ == "__main__":
    print("🚀 Bot đang khởi động...")
    print("✅ Bot đã hoạt động! Mở Telegram và nhắn tin với bot của bạn.")
    print("   Nhấn Ctrl+C để dừng bot.\n")

    # Bắt đầu vòng lặp lắng nghe tin nhắn
    bot.infinity_polling(none_stop=True, interval=0)
