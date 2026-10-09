import { Component, type ErrorInfo, type ReactNode } from "react";

/** Hàng danh sách hỏng thì chỉ hàng ấy báo lỗi, không kéo cả app thành trang trắng (soát UX a10: một dự án có dữ liệu
 *  thiếu làm trắng mọi màn Studio). `fallback` là thứ hiện thay cho hàng. */
export class RowBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Hàng danh sách lỗi", error, info.componentStack);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
