import { S } from "../shared/strings.generated";
import { Button } from "@/shared/ui";
import { MotionRegion } from "@/shared/MotionRegion";

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
  return (
    <MotionRegion className={problem ? className ?? "mt-2" : undefined}>
      {problem && <>
      <p id={id} role="alert" className="text-xs text-danger">
        {problem}
      </p>
      {suggestion && (
        <Button size="sm" variant="ghost" type="button" className="mt-2" onClick={() => onUse(suggestion)}>{S.s_dung_b12f0f49}{suggestion}”
        </Button>
      )}
      </>}
    </MotionRegion>
  );
}
