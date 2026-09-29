import { Button } from "@/shared/ui";

/** Lời từ chối một cách đọc, ngay dưới ô nhập. Máy chủ có bản viết lại đúng chính tả ("Hên-kơ" -> "Hên-cơ",
 *  webui/spelling.py) thì mời dùng bằng một cú bấm - soát UX 29-09: bị từ chối mà không biết sửa chỗ nào. */
export function ReadingProblem({
  id,
  problem,
  suggestion,
  onUse,
  className,
}: {
  id: string;
  problem: string;
  suggestion: string;
  onUse: (spoken: string) => void;
  className?: string;
}) {
  if (!problem) return null;
  return (
    <div className={className ?? "mt-1.5"}>
      <p id={id} role="alert" className="text-xs text-danger">
        {problem}
      </p>
      {suggestion && (
        <Button size="sm" variant="secondary" type="button" className="mt-1.5" onClick={() => onUse(suggestion)}>
          Dùng “{suggestion}”
        </Button>
      )}
    </div>
  );
}
