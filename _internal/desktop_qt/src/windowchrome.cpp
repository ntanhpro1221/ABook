#include "windowchrome.h"

#include <QWKQuick/quickwindowagent.h>

#include <QCursor>
#include <QQuickItem>
#include <QRectF>

WindowChrome::WindowChrome(QObject *parent) : QObject(parent), m_agent(new QWK::QuickWindowAgent(this)) {}

bool WindowChrome::attach(QQuickWindow *window, QQuickItem *titleBar, QQuickItem *minimize, QQuickItem *maximize, QQuickItem *close) {
    if (!m_agent->setup(window))
        return false;
    m_agent->setTitleBar(titleBar);
    m_agent->setSystemButton(QWK::WindowAgentBase::Minimize, minimize);
    m_agent->setSystemButton(QWK::WindowAgentBase::Maximize, maximize);
    m_agent->setSystemButton(QWK::WindowAgentBase::Close, close);
    return true;
}

void WindowChrome::keepClickable(QQuickItem *item) {
    m_agent->setHitTestVisible(item, true);
}

bool WindowChrome::cursorInside(QQuickItem *item) const {
    if (!item || !item->window())
        return false;
    return QRectF(item->mapToGlobal(QPointF(0, 0)), item->size()).contains(QCursor::pos());
}
