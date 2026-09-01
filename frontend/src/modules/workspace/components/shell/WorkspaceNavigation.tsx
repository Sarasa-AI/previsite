import type { WorkspaceViewModel } from "../../presentation/viewmodels/types";

export function WorkspaceNavigation({ viewModel }: { viewModel: WorkspaceViewModel }) {
  const items = [
    { href: "#workspace-patient", label: "بیمار" },
    ...(viewModel.pinCards.length ? [{ href: "#workspace-pinned", label: "موارد مهم" }] : []),
    { href: "#workspace-primary", label: "بررسی اصلی" },
    ...(viewModel.secondaryCards.length ? [{ href: "#workspace-secondary", label: "اطلاعات تکمیلی" }] : []),
    ...(viewModel.deferredCards.length ? [{ href: "#workspace-deferred", label: "موارد تعویق‌شده" }] : []),
    ...(viewModel.queue.length ? [{ href: "#workspace-decisions", label: "صف تصمیم" }] : []),
  ];
  return <nav aria-label="Workspace navigation" className="overflow-x-auto overscroll-x-contain rounded-tai-md border border-tai-border bg-white shadow-tai-sm [scrollbar-gutter:stable]"><ul className="flex min-w-max items-center gap-0.5 px-1.5 py-1">{items.map((item) => <li key={item.href}><a href={item.href} className="inline-flex min-h-8 items-center rounded-tai-sm px-2.5 text-xs font-semibold text-tai-subdued transition-colors hover:bg-tai-teal-soft hover:text-tai-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tai-navy focus-visible:ring-offset-1 sm:px-3">{item.label}</a></li>)}</ul></nav>;
}
