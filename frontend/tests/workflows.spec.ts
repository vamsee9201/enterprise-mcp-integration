import { test, expect, type Page } from "@playwright/test";

async function login(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("button", { name: `Sign in as ${name}` }).click();
  await expect(
    page.getByRole("heading", { name: "My Timesheet", exact: true }),
  ).toBeVisible();
}
async function switchAccount(page: Page, name: string) {
  await page.getByRole("button", { name: "Switch account" }).click();
  await page.getByRole("button", { name: `Sign in as ${name}` }).click();
  await expect(
    page.getByRole("heading", { name: "My Timesheet", exact: true }),
  ).toBeVisible();
}
async function navigate(page: Page, label: string) {
  await page
    .getByRole("navigation")
    .getByRole("button", { name: label, exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: label, exact: true }),
  ).toBeVisible();
}

test("employee logs, edits, submits and manager approves a weekly timesheet", async ({
  page,
}) => {
  await login(page, "Vamsee Krishna");
  await page.getByLabel("Timesheet week").fill("2026-09-28");
  await page.getByRole("button", { name: "Log time", exact: true }).click();
  await page
    .getByLabel("Work description")
    .fill("Implemented shared business services");
  await page.getByRole("button", { name: "Save entry" }).click();
  await expect(
    page.getByRole("cell", {
      name: "Implemented shared business services",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Edit Implemented shared business services" })
    .click();
  await page.getByLabel("Hours", { exact: true }).fill("8");
  await page.getByRole("button", { name: "Save entry" }).click();
  await expect(
    page.getByRole("cell", { name: "8", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/desktop-timesheet.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Submit week" }).click();
  await expect(page.getByText("Waiting for manager review")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Log time", exact: true }),
  ).toBeDisabled();
  await switchAccount(page, "Maya Chen");
  await navigate(page, "Manager Review");
  await page.getByRole("button", { name: "View Vamsee Krishna" }).click();
  await expect(
    page.getByRole("dialog").getByText("Implemented shared business services"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("You’re all caught up")).toBeVisible();
  await switchAccount(page, "Vamsee Krishna");
  await page.getByLabel("Timesheet week").fill("2026-09-28");
  await expect(page.getByText("Reviewed by Maya Chen")).toBeVisible();
  await navigate(page, "Activity");
  await expect(
    page.getByRole("cell", { name: "submit_timesheet", exact: true }),
  ).toBeVisible();
});

test("manager assigns task and employee completes it; directory is searchable", async ({
  page,
}) => {
  await login(page, "Maya Chen");
  await navigate(page, "Tasks");
  await page.getByRole("button", { name: "New task", exact: true }).click();
  await page
    .getByLabel("Title", { exact: true })
    .fill("Prepare portfolio walkthrough");
  await page
    .getByLabel("Assignee", { exact: true })
    .selectOption({ label: "Alex Morgan" });
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByRole("cell", {
      name: "Prepare portfolio walkthrough",
      exact: true,
    }),
  ).toBeVisible();
  await switchAccount(page, "Alex Morgan");
  await navigate(page, "Tasks");
  await expect(
    page.getByRole("button", { name: "New task", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "View Prepare portfolio walkthrough" })
    .click();
  await page.getByLabel("Update task status").selectOption("DONE");
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: "Prepare portfolio walkthrough" })
      .getByText("DONE", { exact: true }),
  ).toBeVisible();
  await navigate(page, "Employee Directory");
  await page.getByLabel("Search records").fill("Vamsee");
  await expect(
    page.getByRole("cell", { name: "Maya Chen", exact: true }),
  ).toBeVisible();
  await navigate(page, "Manager Review");
  await expect(page.getByText("Manager access required")).toBeVisible();
});

test("leave overlap is explained and manager can reject with feedback", async ({
  page,
}) => {
  await login(page, "Alex Morgan");
  await navigate(page, "Leave");
  await page
    .getByRole("button", { name: "Request leave", exact: true })
    .click();
  await page.getByLabel("Start date").fill("2026-10-12");
  await page.getByLabel("End date").fill("2026-10-14");
  await page.getByLabel("Reason (optional)").fill("Family trip");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "Family trip", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Request leave", exact: true })
    .click();
  await page.getByLabel("Start date").fill("2026-10-13");
  await page.getByLabel("End date").fill("2026-10-15");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "overlap",
  );
  await page.getByRole("button", { name: "Close dialog" }).click();
  await switchAccount(page, "Maya Chen");
  await navigate(page, "Manager Review");
  await page.getByRole("button", { name: "View Alex Morgan" }).click();
  await page
    .getByLabel("Reason for rejection")
    .fill("Please coordinate team coverage");
  await page.getByRole("button", { name: "Reject request" }).click();
  await expect(page.getByText("You’re all caught up")).toBeVisible();
  await switchAccount(page, "Alex Morgan");
  await navigate(page, "Leave");
  await page.getByRole("button", { name: "View Alex Morgan" }).click();
  await expect(
    page.getByText("Feedback: Please coordinate team coverage"),
  ).toBeVisible();
});

test("ticket creation, assignment, priority and resolution", async ({
  page,
}) => {
  await login(page, "Sam Rivera");
  await navigate(page, "Support Tickets");
  await page.getByRole("button", { name: "New ticket" }).click();
  await page
    .getByLabel("Title", { exact: true })
    .fill("Laptop cannot connect to VPN");
  await page.getByLabel("Priority", { exact: true }).selectOption("HIGH");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByRole("cell", {
      name: "Laptop cannot connect to VPN",
      exact: true,
    }),
  ).toBeVisible();
  await switchAccount(page, "Maya Chen");
  await navigate(page, "Support Tickets");
  await page
    .getByRole("button", { name: "View Laptop cannot connect to VPN" })
    .click();
  await page
    .getByLabel("Assign ticket", { exact: true })
    .selectOption({ label: "Avery Patel" });
  await page
    .getByRole("button", { name: "View Laptop cannot connect to VPN" })
    .click();
  await page.getByLabel("Priority", { exact: true }).selectOption("MEDIUM");
  await page
    .getByRole("button", { name: "View Laptop cannot connect to VPN" })
    .click();
  await page.getByLabel("Move ticket to").selectOption("IN_PROGRESS");
  await page
    .getByRole("button", { name: "View Laptop cannot connect to VPN" })
    .click();
  await page.getByLabel("Move ticket to").selectOption("RESOLVED");
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: "Laptop cannot connect to VPN" })
      .getByText("RESOLVED", { exact: true }),
  ).toBeVisible();
});

test("workspace picks up an external API change on its next refresh", async ({
  page,
}) => {
  await login(page, "Sam Rivera");
  await page.getByLabel("Timesheet week").fill("2026-10-05");
  await expect(page.getByText("Your week starts here")).toBeVisible();
  const identity = await page.request.get("/api/v1/auth/me");
  const result = await page.request.post("/api/v1/time-entries", {
    headers: {
      Origin: "http://localhost:3010",
      "X-CSRF-Token": (await identity.json()).csrf_token,
    },
    data: {
      project_id: "00000000-0000-4000-8000-000000000101",
      work_date: "2026-10-06",
      hours: 3,
      description: "External service update",
    },
  });
  expect(result.ok()).toBeTruthy();
  await expect(
    page.getByRole("cell", { name: "External service update", exact: true }),
  ).toBeVisible({ timeout: 15000 });
});

test("small viewport keeps navigation and forms usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "Vamsee Krishna");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await navigate(page, "Employee Directory");
  await expect(page.getByLabel("Search records")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/mobile-directory.png",
    fullPage: true,
    animations: "disabled",
  });
});
