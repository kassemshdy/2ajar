import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { locations } from "@/test/fixtures";
import { LocationOptions } from "../location-options";
import { Button } from "./button";
import { Alert, Badge, Card } from "./card";
import { Field, Input, Select, Textarea } from "./input";

describe("UI primitives", () => {
  it("render with variants", () => {
    render(
      <Card>
        <Button variant="whatsapp" size="lg">Go</Button>
        <Badge tone="demo">DEMO</Badge>
        <Badge>Default</Badge>
        <Alert tone="error">Bad</Alert>
        <Alert>Info</Alert>
        <Field label="Name" htmlFor="n" hint="hint text">
          <Input id="n" />
        </Field>
        <Textarea aria-label="t" />
        <Select aria-label="s">
          <LocationOptions locations={locations} locale="ar" />
        </Select>
        <Select aria-label="ids">
          <LocationOptions locations={locations} locale="en" valueKey="id" />
        </Select>
      </Card>,
    );
    expect(screen.getByRole("button", { name: "Go" }).className).toContain("bg-whatsapp");
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByText("hint text")).toBeInTheDocument();
    expect(screen.getAllByRole("status")).toHaveLength(2);
    expect(screen.getByRole("option", { name: /الحمرا/ })).toHaveValue("hamra");
    expect(screen.getByRole("option", { name: /Hamra/ })).toHaveValue("a1");
  });
});
