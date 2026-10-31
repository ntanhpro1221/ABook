// Danh sách chương của cuốn đang nạp (trang sách, ngăn Chương, cột phải của Đang nghe khi chưa có chữ chạy theo).
// Chỉ đổi dòng thật sự đổi: sang chương khác chỉ báo hai dòng (chương cũ, chương mới), không dựng lại cả danh sách.
#pragma once

#include "playerlogic.h"

#include <QAbstractListModel>
#include <QtQml/qqmlregistration.h>

class ChaptersModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("Có sẵn trong Player.chapters")
    Q_PROPERTY(int count READ count NOTIFY countChanged)
public:
    enum Role {
        IdRole = Qt::UserRole + 1,
        NumberRole,
        TitleRole,
        SubtitleRole,
        FullTitleRole,
        LengthRole,     // "26 phút" hay "" (chương chỉ có chữ không có gì riêng để nói)
        StatusRole,     // "" | "Chưa có audio" | "Đang thu âm…"
        PlayableRole,
        TextOnlyRole,
        DoneRole,
        ProgressRole,   // 0..1 đã nghe
        CurrentRole,
    };
    explicit ChaptersModel(QObject *parent = nullptr) : QAbstractListModel(parent) {}

    int rowCount(const QModelIndex &parent = {}) const override { return parent.isValid() ? 0 : int(m_rows.size()); }
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;
    int count() const { return int(m_rows.size()); }

    /// Nạp sách mới (đổi cả danh sách).
    void setBook(const PlayerLogic::Book &book);
    /// Dấu nghe của sách đổi (lời đáp progress): chỉ báo dòng nào thật sự đổi.
    void refreshStates(const PlayerLogic::Book &book);
    void setCurrent(int chapterId);
    /// Hàng của chương, hay -1.
    Q_INVOKABLE int rowOf(int chapterId) const;

signals:
    void countChanged();

private:
    struct Row {
        PlayerLogic::Chapter chapter;
        bool done = false;
        double progress = 0;
        QString length;
        QString status;
    };
    static Row make(const PlayerLogic::Book &book, const PlayerLogic::Chapter &chapter);
    QList<Row> m_rows;
    bool m_producing = false;
    int m_current = -1;
};
