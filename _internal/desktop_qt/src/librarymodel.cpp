#include "librarymodel.h"

#include "playerlogic.h"

#include <QJsonObject>
#include <cmath>

LibraryModel::LibraryModel(QObject *parent) : QAbstractListModel(parent) {}

int LibraryModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : int(m_books.size());
}

QHash<int, QByteArray> LibraryModel::roleNames() const {
    return {{IdRole, "bookId"}, {TitleRole, "title"}, {SubtitleRole, "subtitle"}, {CoverKeyRole, "coverKey"},
            {ProgressRole, "progress"}, {SourceRole, "source"}};
}

QVariant LibraryModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() < 0 || index.row() >= int(m_books.size()))
        return {};
    const Book &b = m_books[size_t(index.row())];
    switch (role) {
    case IdRole: return b.id;
    case TitleRole: return b.title;
    case SubtitleRole: return b.subtitle;
    case CoverKeyRole: return b.coverKey;
    case ProgressRole: return b.progress;
    case SourceRole: return b.source;
    }
    return {};
}

QString LibraryModel::durationText(double seconds) {
    const int minutes = int(std::lround(seconds / 60.0));
    if (minutes <= 0)
        return {};
    const int h = minutes / 60, m = minutes % 60;
    if (h == 0)
        return QStringLiteral("%1 phút").arg(m);
    return m == 0 ? QStringLiteral("%1 giờ").arg(h) : QStringLiteral("%1 giờ %2 phút").arg(h).arg(m);
}

void LibraryModel::setBooks(const QJsonArray &array) {
    std::vector<Book> books;
    books.reserve(size_t(array.size()));
    for (const QJsonValue &value : array) {
        const QJsonObject o = value.toObject();
        Book b;
        b.raw = o;
        b.id = o.value(QStringLiteral("id")).toString();
        if (b.id.isEmpty())
            continue;
        b.title = o.value(QStringLiteral("title")).toString();
        b.author = o.value(QStringLiteral("author")).toString();
        b.narrator = o.value(QStringLiteral("narrator")).toString();
        b.duration = o.value(QStringLiteral("duration")).toDouble();
        b.chaptersTotal = o.value(QStringLiteral("chaptersTotal")).toInt();
        b.chaptersAvailable = o.value(QStringLiteral("chaptersAvailable")).toInt();
        b.producing = o.value(QStringLiteral("producing")).toBool();
        b.complete = o.value(QStringLiteral("complete")).toBool();
        b.lastChapter = o.value(QStringLiteral("lastChapterTitle")).toString();
        const QJsonObject progress = o.value(QStringLiteral("progress")).toObject();
        b.progress = progress.value(QStringLiteral("finished")).toBool() ? 1.0 : progress.value(QStringLiteral("fraction")).toDouble();
        const QJsonValue remote = o.value(QStringLiteral("remote"));
        if (remote.isObject())
            b.source = remote.toObject().value(QStringLiteral("computer")).toString();
        b.coverKey = PlayerLogic::coverKeyOf(b.id, o.value(QStringLiteral("cover")).toObject());
        QStringList detail;
        if (b.producing)
            detail << QStringLiteral("Đang làm · %1/%2 chương").arg(b.chaptersAvailable).arg(b.chaptersTotal);
        else if (const QString d = durationText(b.duration); !d.isEmpty())
            detail << d;
        b.detail = detail.join(QStringLiteral(" · "));
        b.subtitle = b.producing || b.author.isEmpty() ? b.detail : b.author;
        books.push_back(std::move(b));
    }

    bool same = books.size() == m_books.size();
    for (size_t i = 0; same && i < books.size(); ++i)
        same = books[i].sameShelf(m_books[i]);
    const int before = int(m_books.size());
    if (same) {
        m_books = std::move(books);
        if (!m_books.empty())
            emit dataChanged(index(0), index(int(m_books.size()) - 1));
    } else {
        beginResetModel();
        m_books = std::move(books);
        endResetModel();
    }
    if (before != int(m_books.size()))
        emit countChanged();
    ++m_revision;
    emit revisionChanged();
    if (!m_error.isEmpty()) {
        m_error.clear();
        emit errorChanged();
    }
}

void LibraryModel::setError(const QString &message) {
    if (m_error == message)
        return;
    m_error = message;
    emit errorChanged();
}

QVariantMap LibraryModel::book(int row) const {
    if (row < 0 || row >= int(m_books.size()))
        return {};
    const Book &b = m_books[size_t(row)];
    QVariantMap result = b.raw.toVariantMap();
    const QVariantMap display = {{QStringLiteral("bookId"), b.id}, {QStringLiteral("title"), b.title}, {QStringLiteral("author"), b.author}, {QStringLiteral("subtitle"), b.subtitle},
            {QStringLiteral("narrator"), b.narrator}, {QStringLiteral("detail"), b.detail}, {QStringLiteral("coverKey"), b.coverKey},
            {QStringLiteral("progress"), b.progress}, {QStringLiteral("source"), b.source},
            {QStringLiteral("chapters"), b.chaptersTotal}, {QStringLiteral("lastChapter"), b.lastChapter},
            {QStringLiteral("producing"), b.producing}};
    for (auto i = display.cbegin(); i != display.cend(); ++i) result.insert(i.key(), i.value());
    // Keep the structured progress next to the display fraction. Filtering and the
    // continue card need finished/caughtUp/heardSeconds, not a guessed fraction.
    result.insert(QStringLiteral("listeningProgress"), b.raw.value(QStringLiteral("progress")).toVariant());
    return result;
}
