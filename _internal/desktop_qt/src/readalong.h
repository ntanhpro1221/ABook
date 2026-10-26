// "Đọc theo": văn bản chương chạy theo giọng. Một bộ điều khiển dùng chung (singleton) cho màn Đang nghe: nạp kịch bản chương đang phát, tìm câu / chữ
// đang đọc theo vị trí bộ phát, đưa cho QML hình chữ nhật của câu / chữ ấy (từ QTextLayout của chính TextEdit) và việc "bấm câu để nghe từ đó".
// Luật thuần ở scriptlogic.h. CHỈ phát tín hiệu khi câu / chữ thật sự đổi: không có gì trong QML bị đánh giá lại theo nhịp đồng hồ.
#pragma once

#include "player.h"
#include "scriptlogic.h"

#include <QAbstractListModel>
#include <QColor>
#include <QObject>
#include <QQmlEngine>
#include <QQuickTextDocument>
#include <QTimer>
#include <QVariantList>
#include <QtQml/qqmlregistration.h>

/// Các đoạn của chương: một dòng một đoạn (ListView ảo hoá, chỉ dựng đoạn đang thấy).
class ScriptModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("Có sẵn trong ReadAlong.paragraphs")
public:
    enum Role { TextRole = Qt::UserRole + 1, KindRole, SpeakerRole, FirstRole, CountRole };
    explicit ScriptModel(QObject *parent = nullptr) : QAbstractListModel(parent) {}
    int rowCount(const QModelIndex &parent = {}) const override { return parent.isValid() ? 0 : int(m_script.paragraphs.size()); }
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;
    void set(ScriptLogic::Script script);
    const ScriptLogic::Script &script() const { return m_script; }

private:
    ScriptLogic::Script m_script;
};

class ReadAlong : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    /// Màn đang hiện chữ: chỉ khi true mới nạp kịch bản và chạy nhịp.
    Q_PROPERTY(bool active READ active WRITE setActive NOTIFY activeChanged)
    /// "idle" | "loading" | "ready" | "failed"
    Q_PROPERTY(QString status READ status NOTIFY statusChanged)
    /// Kịch bản có mốc theo giây (đọc theo được).
    Q_PROPERTY(bool timed READ timed NOTIFY statusChanged)
    Q_PROPERTY(ScriptModel *paragraphs READ paragraphs CONSTANT)
    Q_PROPERTY(int currentPara READ currentPara NOTIFY currentParaChanged)
    Q_PROPERTY(int currentSegment READ currentSegment NOTIFY currentSegmentChanged)
    Q_PROPERTY(int currentWord READ currentWord NOTIFY currentWordChanged)
    /// Số lần tính lại câu / chữ đang đọc (đo: bench.cpp).
    Q_PROPERTY(quint64 evaluations READ evaluations CONSTANT)
    /// Số lần câu / chữ / đoạn đang đọc thật sự đổi (đo).
    Q_PROPERTY(quint64 changes READ changes CONSTANT)
public:
    explicit ReadAlong(Player *player, PlayerNet *net, QObject *parent = nullptr);
    static ReadAlong *create(QQmlEngine *, QJSEngine *);
    static void setInstance(ReadAlong *instance);

    bool active() const { return m_active; }
    void setActive(bool active);
    QString status() const { return m_status; }
    bool timed() const { return m_status == QLatin1String("ready") && m_model.script().timed && !m_model.script().segments.isEmpty(); }
    ScriptModel *paragraphs() { return &m_model; }
    int currentPara() const { return m_para; }
    int currentSegment() const { return m_segment; }
    int currentWord() const { return m_word; }
    quint64 evaluations() const { return m_evaluations; }
    quint64 changes() const { return m_changes; }
    /// Tắt màn chữ bao lâu thì bỏ kịch bản (ms); thử đặt ngắn.
    void setDropMs(int ms) { m_drop.setInterval(ms); }

    /// Hình chữ nhật (toạ độ của TextEdit) từng dòng của câu `segment` (thứ tự toàn chương) nằm trong đoạn `paragraph`; rỗng nếu câu không thuộc đoạn.
    Q_INVOKABLE QVariantList sentenceRects(QQuickTextDocument *document, int paragraph, int segment) const;
    Q_INVOKABLE QVariantList wordRects(QQuickTextDocument *document, int paragraph, int segment, int word) const;
    /// Câu dưới vị trí ký tự `position` của đoạn (toàn chương), hay -1.
    Q_INVOKABLE int segmentAt(int paragraph, int position) const;
    /// Đặt chiều cao dòng cố định cho mọi khối của tài liệu (TextEdit không có lineHeight).
    Q_INVOKABLE void setLineHeight(QQuickTextDocument *document, qreal pixels) const;
    /// Tô màu "đã nghe": đoạn trước đoạn đang đọc nhạt hết, đoạn đang đọc nhạt tới hết câu trước câu đang đọc, đoạn sau giữ màu thường.
    Q_INVOKABLE void shade(QQuickTextDocument *document, int paragraph, const QColor &heard, const QColor &normal) const;
    /// Bấm vào ký tự `position` của đoạn: nghe từ chữ / câu ấy. Trả false nếu không nghe được.
    Q_INVOKABLE bool listenFrom(int paragraph, int position);
    /// Luật cuộn theo (follow.ts), toạ độ cùng một hệ.
    Q_INVOKABLE QString placement(qreal top, qreal bottom, qreal viewTop, qreal viewBottom) const;
    Q_INVOKABLE bool needsFollow(qreal top, qreal bottom, qreal viewTop, qreal viewBottom) const;
    Q_INVOKABLE qreal followTop(qreal top, qreal viewTop, qreal viewBottom, qreal scrollTop) const;
    Q_INVOKABLE int settleMs() const { return FollowLogic::kSettleMs; }

    /// Tính lại câu / chữ đang đọc theo vị trí bộ phát (QTimer và tín hiệu đồng hồ gọi; test gọi tay).
    void update();
    /// Nạp ngay kịch bản chương đang phát; bình thường tự nạp khi `active` hay khi sang chương khác.
    void reload();

signals:
    void activeChanged();
    void statusChanged();
    void currentParaChanged();
    void currentSegmentChanged();
    void currentWordChanged();
    /// Người vừa bấm một câu để nghe từ đó: màn đọc theo lại.
    void listened();

private:
    void scheduleReload();
    void apply(ScriptLogic::Script script);
    void setStatus(const QString &status);
    void prefetchNext();
    void restartTicker();
    void dropScript();

    Player *m_player;
    PlayerNet *m_net;
    ScriptModel m_model;
    QTimer m_ticker;
    QTimer m_reload;
    QTimer m_drop;      // màn chữ đã tắt một lúc: bỏ kịch bản chương (RAM khi nghe với cửa sổ thu nhỏ / ở màn khác)
    bool m_active = false;
    QString m_status = QStringLiteral("idle");
    QString m_loadedBook;
    int m_loadedChapter = 0;
    quint64 m_seq = 0;
    int m_para = -1;
    int m_segment = -1;
    int m_word = -1;
    quint64 m_evaluations = 0;
    quint64 m_changes = 0;
    // Chương kế nạp sẵn khi sắp hết chương: sang chương không chớp "đang mở".
    int m_prefetchChapter = 0;
    QString m_prefetchBook;
    bool m_prefetching = false;
    ScriptLogic::Script m_prefetched;
};
