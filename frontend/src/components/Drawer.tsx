import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "./ui";

type DrawerProps = { open: boolean; onClose: () => void; title: string; children: ReactNode };

/** <dialog> nativo: prende o foco, fecha com Esc e devolve o foco ao botão que abriu. */
export function Drawer({ open, onClose, title, children }: DrawerProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (open && !dialog?.open) dialog?.showModal();
    if (!open && dialog?.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-label={title}
      className="m-0 ml-auto h-dvh max-h-none w-full max-w-md overflow-y-auto border-l border-line bg-surface p-6 text-text backdrop:bg-bg/80"
    >
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-title font-semibold">{title}</h2>
        <Button onClick={onClose}>Fechar</Button>
      </div>
      <div className="mt-6">{open && children}</div>
    </dialog>
  );
}
