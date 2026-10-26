#include "chaptersmodel.h"

QHash<int, QByteArray> ChaptersModel::roleNames() const {
    return {{IdRole, "chapterId"},       {NumberRole, "number"},     {TitleRole, "title"},       {SubtitleRole, "subtitle"},
            {FullTitleRole, "fullTitle"}, {LengthRole, "length"},     {StatusRole, "status"},     {PlayableRole, "playable"},
            {TextOnlyRole, "textOnly"},   {DoneRole, "done"},         {ProgressRole, "progress"}, {CurrentRole, "current"}};
}

QVariant ChaptersModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() < 0 || index.row() >= m_rows.size())
        return {};
    const Row &row = m_rows.at(index.row());
    switch (role) {
    case IdRole: return row.chapter.id;
    case NumberRole: return row.chapter.index;
    case TitleRole: return row.chapter.title;
    case SubtitleRole: return row.chapter.subtitle;
    case FullTitleRole: return row.chapter.fullTitle;
    case LengthRole: return row.length;
    case StatusRole: return row.status;
    case PlayableRole: return PlayerLogic::canPlay(row.chapter);
    case TextOnlyRole: return row.chapter.textOnly;
    case DoneRole: return row.done;
    case ProgressRole: return row.progress;
    case CurrentRole: return row.chapter.id == m_current;
    default: return {};
    }
}

ChaptersModel::Row ChaptersModel::make(const PlayerLogic::Book &book, const PlayerLogic::Chapter &chapter) {
    Row row;
    row.chapter = chapter;
    const PlayerLogic::ChapterState state = book.states.value(chapter.id);
    row.done = state.done;
    const double length = PlayerLogic::knownDuration(book, chapter);
    row.progress = state.done ? 1.0 : (length > 0 ? qMin(1.0, state.heard / length) : 0.0);
    // chapterSubline của bản web: dòng phụ = tên chương khi có phụ đề, rồi độ dài; chương chỉ có chữ không có gì riêng để nói.
    row.length = chapter.available ? PlayerLogic::formatLength(chapter.duration) : QString();
    if (!chapter.available && !chapter.textOnly)
        row.status = book.producing ? QStringLiteral("Đang thu âm…") : QStringLiteral("Chưa có audio");
    return row;
}

void ChaptersModel::setBook(const PlayerLogic::Book &book) {
    beginResetModel();
    m_rows.clear();
    m_rows.reserve(book.chapters.size());
    for (const PlayerLogic::Chapter &chapter : book.chapters)
        m_rows.append(make(book, chapter));
    m_producing = book.producing;
    endResetModel();
    emit countChanged();
}

void ChaptersModel::refreshStates(const PlayerLogic::Book &book) {
    for (int i = 0; i < m_rows.size() && i < book.chapters.size(); ++i) {
        const Row fresh = make(book, book.chapters.at(i));
        Row &row = m_rows[i];
        if (row.done == fresh.done && qFuzzyCompare(1 + row.progress, 1 + fresh.progress) && row.length == fresh.length && row.status == fresh.status)
            continue;
        row = fresh;
        const QModelIndex at = index(i);
        emit dataChanged(at, at, {DoneRole, ProgressRole, LengthRole, StatusRole, PlayableRole});
    }
}

void ChaptersModel::setCurrent(int chapterId) {
    if (chapterId == m_current)
        return;
    const int before = rowOf(m_current);
    m_current = chapterId;
    const int now = rowOf(chapterId);
    if (before >= 0)
        emit dataChanged(index(before), index(before), {CurrentRole});
    if (now >= 0)
        emit dataChanged(index(now), index(now), {CurrentRole});
}

int ChaptersModel::rowOf(int chapterId) const {
    for (int i = 0; i < m_rows.size(); ++i)
        if (m_rows.at(i).chapter.id == chapterId)
            return i;
    return -1;
}
