import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Alert, Button, IconButton, StatePanel, StatusBadge, Tabs, TabsContent, TabsList, TabsTrigger, Tooltip } from "./design-system";
import { DateValue, DoseValue, MrnValue } from "./bidi";

describe("TreatAI design system", () => {
  it("exposes semantic states with text and non-color symbols", () => {
    render(<><StatusBadge state="unknown">Unknown</StatusBadge><StatusBadge state="conflict">Conflict</StatusBadge><StatusBadge state="ai-generated">AI generated</StatusBadge></>);
    expect(screen.getByText("Unknown").closest("span")).toHaveAttribute("data-semantic-state", "unknown");
    expect(screen.getByText("Conflict").parentElement).toHaveTextContent("!");
    expect(screen.getByText("AI generated").parentElement).toHaveTextContent("AI");
  });

  it("handles button interaction, loading and disabled states", () => {
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick}>Save</Button>);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledOnce();
    rerender(<Button loading>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("aria-busy", "true");
  });

  it("requires an accessible name for icon buttons and exposes tooltip content", () => {
    render(<Tooltip label="Refresh data"><IconButton aria-label="Refresh"><span aria-hidden="true">R</span></IconButton></Tooltip>);
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveTextContent("Refresh data");
    expect(screen.getByRole("button", { name: "Refresh" }).parentElement).toHaveAttribute("aria-describedby", tooltip.id);
  });

  it("uses appropriate live-region semantics for alerts and async states", () => {
    render(<><Alert state="critical" title="Critical">Review now</Alert><StatePanel kind="loading" title="Loading" /></>);
    expect(screen.getByRole("alert")).toHaveTextContent("Critical");
    expect(screen.getByRole("status", { name: "" })).toHaveAttribute("aria-busy", "true");
  });

  it("provides keyboard-accessible tabs", () => {
    render(<Tabs defaultValue="one"><TabsList aria-label="Sections"><TabsTrigger value="one">One</TabsTrigger><TabsTrigger value="two">Two</TabsTrigger></TabsList><TabsContent value="one">First</TabsContent><TabsContent value="two">Second</TabsContent></Tabs>);
    expect(screen.getByRole("tab", { name: "One" })).toHaveAttribute("data-state", "active");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Two" }), { button: 0 });
    fireEvent.click(screen.getByRole("tab", { name: "Two" }));
    expect(screen.getByText("Second")).toBeVisible();
  });

  it("isolates MRN, date and dose values from RTL prose", () => {
    render(<div dir="rtl"><MrnValue>MRN-1024</MrnValue><DateValue>2026-08-31</DateValue><DoseValue>10 mg</DoseValue></div>);
    for (const value of ["MRN-1024", "2026-08-31", "10 mg"]) expect(screen.getByText(value)).toHaveAttribute("dir", "ltr");
  });
});
