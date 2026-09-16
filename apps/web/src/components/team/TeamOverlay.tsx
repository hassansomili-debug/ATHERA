"use client";

import { useCallback, useEffect, useRef, type ReactNode } from "react";

/**
 * طبقةٌ واحدةٌ لكلِّ ما يُفتح فوق الصفحة — لوحٌ جانبيّ أو نافذة (RC-T1C UX-1).
 *
 * **ولمَ بدائيّةٌ واحدة لا ثلاث.** كانت شاشةُ الفريق تعرض كلَّ شيءٍ في
 * عمودٍ واحد، فلمّا صار التفصيلُ يُفتح عند الطلب احتجنا ثلاثةَ مواضع
 * تُفتح: تفصيلُ العضو، ونموذجُ الدعوة، ورمزُها. وثلاثُ نسخٍ من «افتح
 * فوق الصفحة» تفترق بأوّل تعديل: تُنسى `Escape` في واحدة، ويضيع
 * التركيزُ في أخرى، ولا تُغلق الثالثةُ بالخلفية.
 *
 * **وما تضمنه هذه الطبقة:**
 *
 *   • `role="dialog"` و`aria-modal` وعنوانٌ مربوطٌ بـ`aria-labelledby` —
 *     فقارئُ الشاشة يعرف أنّه دخل طبقةً، ويعرف اسمَها.
 *   • `Escape` تُغلق، والخلفيّةُ تُغلق، وزرُّ الإغلاق له اسمٌ مقروء.
 *   • **التركيزُ يدخل ويعود**: يُنقل إلى الطبقة عند الفتح، ويُردّ إلى
 *     العنصر الذي فتحها عند الإغلاق — وإلّا وجد مستعملُ المفاتيح نفسَه
 *     في أوّل الصفحة بعد كلِّ إغلاق.
 *   • `Tab` يلتفّ داخل الطبقة: طبقةٌ مشروطةٌ يخرج منها التركيزُ إلى
 *     صفحةٍ محجوبةٍ بصريًّا تعني مستعملًا يكتب في ما لا يرى.
 *
 * **ولا تُقفل الصفحةُ خلفها بـ`inert`**: المتصفّحاتُ تختلف فيها، والالتفافُ
 * أعلاه يكفي لما تفعله هذه الشاشة.
 *
 * والاتجاهُ منطقيّ لا يساريّ: اللوحُ يدخل من `inset-inline-end`، فيصير في
 * العربيّة يسارًا وفي الإنجليزيّة يمينًا بلا فرعٍ في الشيفرة.
 */
const FOCUSABLE = [
  "a[href]", "button:not([disabled])", "input:not([disabled])",
  "select:not([disabled])", "textarea:not([disabled])", "[tabindex]:not([tabindex='-1'])",
].join(",");

export function TeamOverlay({
  open,
  onClose,
  title,
  titleId,
  variant = "drawer",
  closeLabel,
  footer,
  children,
  testId,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  /** يربط العنوانَ بالطبقة — ويجب أن يكون فريدًا في الصفحة. */
  titleId: string;
  /** `drawer` لوحٌ جانبيّ للتفصيل، و`modal` نافذةٌ للفعل القصير. */
  variant?: "drawer" | "modal";
  closeLabel: string;
  footer?: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  const surface = useRef<HTMLDivElement | null>(null);
  // العنصرُ الذي فتح الطبقة — يُردّ إليه التركيزُ عند الإغلاق.
  const opener = useRef<HTMLElement | null>(null);

  const keydown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !surface.current) return;
      const nodes = Array.from(
        surface.current.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter((node) => node.offsetParent !== null);
      if (!nodes.length) return;
      const first = nodes[0]!;
      const last = nodes[nodes.length - 1]!;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !surface.current.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement as HTMLElement | null;
    // **أوّلُ ما يُركَّز هو أوّلُ ما يُفعل** — لا زرُّ الإغلاق: من فتح
    // لوحًا يريد ما فيه، وردُّه إلى «أغلق» يجعل الطبقةَ تبدو خاطئة.
    const target = surface.current?.querySelector<HTMLElement>(FOCUSABLE);
    (target ?? surface.current)?.focus();
    document.addEventListener("keydown", keydown, true);
    return () => {
      document.removeEventListener("keydown", keydown, true);
      opener.current?.focus?.();
    };
  }, [open, keydown]);

  if (!open) return null;

  return (
    <div
      className={`overlay overlay-${variant}`}
      // والنقرُ على الخلفيّةِ يُغلق، والنقرُ داخل السطح لا يصل إلى هنا.
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="overlay-surface"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        ref={surface}
        data-testid={testId}
      >
        <header className="overlay-head">
          <h2 id={titleId} className="overlay-title">{title}</h2>
          <button
            type="button"
            className="overlay-close"
            aria-label={closeLabel}
            data-testid={testId ? `${testId}-close` : undefined}
            onClick={onClose}
          >
            ×
          </button>
        </header>
        <div className="overlay-body">{children}</div>
        {footer ? <footer className="overlay-foot">{footer}</footer> : null}
      </div>
    </div>
  );
}
