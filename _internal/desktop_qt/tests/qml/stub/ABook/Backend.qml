pragma Singleton
import QtQuick

// Chỗ của Backend (C++) trong bộ thử thanh bên: ConnectionChip chỉ đọc trạng thái.
QtObject {
    enum State { Starting, Ready, Failed }
    property int state: 1
}
