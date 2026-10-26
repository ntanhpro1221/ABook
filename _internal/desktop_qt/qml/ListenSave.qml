import QtQuick
import ABook

// Lưu một tuỳ chọn Cài đặt như usePreferences().update của bản web: thành công thì Api.preferences đã gộp giá trị mới (giao diện đổi theo);
// thất bại thì giá trị cũ ở nguyên và có lời "Chưa lưu được cài đặt" kèm lời máy chủ (toast.error(title, {description})).
QtObject {
    // `done(data, error)` chỉ chạy khi lệnh PUT thật sự đi (Api.update bỏ qua lệnh đến lúc đang lưu một lệnh khác).
    function update(changes, done) {
        Api.update(changes, function(data, error) {
            if (error) Api.notice = "Chưa lưu được cài đặt\n" + error
            if (done) done(data, error)
        })
    }
}
