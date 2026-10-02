import { test, expect, type Page } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/v1/__test/reset");
  expect(response.ok()).toBeTruthy();
});

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
  await login(page, "Dinesh Chugtai");
  await page.getByLabel("Timesheet week").fill("2026-09-28");
  await expect(
    page.getByRole("table", { name: "Weekly project hours" }),
  ).toBeVisible();
  await expect(
    page.getByRole("rowheader", { name: "Compression Engine", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("rowheader", { name: "PiperNet", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Compression Engine on 09/30: 0 hours",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Compression Engine on 09/30: 0 hours",
      exact: true,
    })
    .click();
  await expect(page.getByLabel("Project", { exact: true })).toHaveValue(
    "00000000-0000-4000-8000-000000000101",
  );
  await expect(page.getByLabel("Work date")).toHaveValue("2026-09-30");
  await page
    .getByLabel("Work description")
    .fill("Implemented shared business services");
  await page.getByRole("button", { name: "Save entry" }).click();
  await page
    .getByRole("button", {
      name: "Compression Engine on 09/30: 7 hours",
      exact: true,
    })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByText("Implemented shared business services", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Edit Implemented shared business services" })
    .click();
  await page.getByLabel("Hours", { exact: true }).fill("8");
  await page.getByRole("button", { name: "Save entry" }).click();
  await expect(
    page.getByRole("button", {
      name: "Compression Engine on 09/30: 8 hours",
      exact: true,
    }),
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
  await switchAccount(page, "Bertram Gilfoyle");
  await navigate(page, "Manager Review");
  await page.getByRole("button", { name: "View Dinesh Chugtai" }).click();
  await expect(
    page.getByRole("dialog").getByText("Implemented shared business services"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("You’re all caught up")).toBeVisible();
  await switchAccount(page, "Dinesh Chugtai");
  await page.getByLabel("Timesheet week").fill("2026-09-28");
  await expect(page.getByText("Reviewed by Bertram Gilfoyle")).toBeVisible();
  await navigate(page, "Activity");
  await expect(
    page.getByRole("cell", { name: "submit_timesheet", exact: true }),
  ).toBeVisible();
});

test("manager assigns task and employee completes it; directory is searchable", async ({
  page,
}) => {
  await login(page, "Bertram Gilfoyle");
  await navigate(page, "Tasks");
  await page.getByRole("button", { name: "New task", exact: true }).click();
  await page
    .getByLabel("Title", { exact: true })
    .fill("Prepare portfolio walkthrough");
  await page
    .getByLabel("Assignee", { exact: true })
    .selectOption({ label: "Jared Dunn" });
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByRole("cell", {
      name: "Prepare portfolio walkthrough",
      exact: true,
    }),
  ).toBeVisible();
  await switchAccount(page, "Jared Dunn");
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
  await page.getByLabel("Search records").fill("Dinesh");
  await expect(
    page.getByRole("cell", { name: "Bertram Gilfoyle", exact: true }),
  ).toBeVisible();
  await navigate(page, "Manager Review");
  await expect(page.getByText("Manager access required")).toBeVisible();
});

test("leave overlap is explained and manager can reject with feedback", async ({
  page,
}) => {
  await login(page, "Jared Dunn");
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
  await switchAccount(page, "Bertram Gilfoyle");
  await navigate(page, "Manager Review");
  await page.getByRole("button", { name: "View Jared Dunn" }).click();
  await page
    .getByLabel("Reason for rejection")
    .fill("Please coordinate team coverage");
  await page.getByRole("button", { name: "Reject request" }).click();
  await expect(page.getByText("You’re all caught up")).toBeVisible();
  await switchAccount(page, "Jared Dunn");
  await navigate(page, "Leave");
  await page.getByRole("button", { name: "View Jared Dunn" }).click();
  await expect(
    page.getByText("Feedback: Please coordinate team coverage"),
  ).toBeVisible();
});

test("ticket creation, assignment, priority and resolution", async ({
  page,
}) => {
  await login(page, "Erlich Bachman");
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
  await switchAccount(page, "Bertram Gilfoyle");
  await navigate(page, "Support Tickets");
  await page
    .getByRole("button", { name: "View Laptop cannot connect to VPN" })
    .click();
  await page
    .getByLabel("Assign ticket", { exact: true })
    .selectOption({ label: "Richard Hendricks" });
  await page
    .getByRole("button", { name: "View Laptop cannot connect to VPN" })
    .click();
  await page.getByLabel("Priority", { exact: true }).selectOption("MEDIUM");
  await page
    .getByRole("button", { name: "View Laptop cannot connect to VPN" })
    .click();
  await page.getByLabel("Ticket status").selectOption("IN_PROGRESS");
  await page
    .getByRole("button", { name: "View Laptop cannot connect to VPN" })
    .click();
  await page.getByLabel("Ticket status").selectOption("RESOLVED");
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
  await login(page, "Erlich Bachman");
  await page.getByLabel("Timesheet week").fill("2026-10-05");
  await expect(
    page.getByRole("button", {
      name: "Compression Engine on 10/06: 0 hours",
      exact: true,
    }),
  ).toBeVisible();
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
    page.getByRole("button", {
      name: "Compression Engine on 10/06: 3 hours",
      exact: true,
    }),
  ).toBeVisible({ timeout: 15000 });
});

test("small viewport keeps navigation and forms usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "Dinesh Chugtai");
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

test("weekly grid aggregates entries, deletes individual entries, and resets empty weeks to zero", async ({
  page,
}) => {
  await login(page, "Jared Dunn");
  await page.getByLabel("Timesheet week").fill("2026-11-02");
  await expect(page.getByRole("columnheader")).toHaveCount(8);
  for (const date of [
    "11/02",
    "11/03",
    "11/04",
    "11/05",
    "11/06",
    "11/07",
    "11/08",
  ]) {
    await expect(
      page.getByRole("columnheader").filter({ hasText: date }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: `Compression Engine on ${date}: 0 hours`,
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: `PiperNet on ${date}: 0 hours`,
        exact: true,
      }),
    ).toBeVisible();
  }
  await expect(
    page.getByRole("button", { name: "Submit week" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "PiperNet on 11/04: 0 hours", exact: true })
    .click();
  await expect(page.getByLabel("Project", { exact: true })).toHaveValue(
    "00000000-0000-4000-8000-000000000102",
  );
  await page.getByLabel("Hours", { exact: true }).fill("1.25");
  await page.getByLabel("Work description").fill("Launch preparation");
  await page.getByRole("button", { name: "Save entry" }).click();
  await page
    .getByRole("button", { name: "PiperNet on 11/04: 1.25 hours", exact: true })
    .click();
  await page.getByRole("button", { name: "Add entry", exact: true }).click();
  await expect(page.getByLabel("Work date")).toHaveValue("2026-11-04");
  await page.getByLabel("Hours", { exact: true }).fill("0.75");
  await page.getByLabel("Work description").fill("Launch follow-up");
  await page.getByRole("button", { name: "Save entry" }).click();
  await page
    .getByRole("button", { name: "PiperNet on 11/04: 2 hours", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByText("Launch preparation", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("Launch follow-up", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Delete Launch follow-up", exact: true })
    .click();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await expect(
    page.getByRole("button", {
      name: "PiperNet on 11/04: 1.25 hours",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Next week" }).click();
  await expect(
    page.getByRole("button", {
      name: "PiperNet on 11/11: 0 hours",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Submit week" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Previous week" }).click();
  await expect(
    page.getByRole("button", {
      name: "PiperNet on 11/04: 1.25 hours",
      exact: true,
    }),
  ).toBeVisible();
});

test("logs and submits hours without a description", async ({ page }) => {
  await login(page, "Jared Dunn");
  await page.getByLabel("Timesheet week").fill("2026-12-14");
  await page
    .getByRole("button", { name: "PiperNet on 12/16: 0 hours", exact: true })
    .click();
  await expect(
    page.getByLabel("Work description (optional)", { exact: true }),
  ).not.toHaveAttribute("required", "");
  await page.getByLabel("Hours", { exact: true }).fill("6");
  await page.getByRole("button", { name: "Save entry" }).click();
  await page
    .getByRole("button", { name: "PiperNet on 12/16: 6 hours", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Edit 6-hour entry", exact: true })
    .click();
  await page.getByRole("button", { name: "Save entry" }).click();
  await expect(
    page.getByRole("button", {
      name: "PiperNet on 12/16: 6 hours",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Submit week" }).click();
  await expect(page.getByText("Waiting for manager review")).toBeVisible();
});

test("rejected timesheet can be corrected, resubmitted and approved", async ({
  page,
}) => {
  await login(page, "Erlich Bachman");
  await page.getByLabel("Timesheet week").fill("2027-03-01");
  await page
    .getByRole("button", { name: "PiperNet on 03/02: 0 hours", exact: true })
    .click();
  await page.getByLabel("Hours", { exact: true }).fill("8.25");
  await page.getByLabel("Work description").fill("QA correction lifecycle");
  await page.getByRole("button", { name: "Save entry" }).click();
  await page
    .getByRole("button", {
      name: "Compression Engine on 03/02: 0 hours",
      exact: true,
    })
    .click();
  await page.getByLabel("Hours", { exact: true }).fill("16");
  await page.getByRole("button", { name: "Save entry" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "Daily hours cannot exceed 24",
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "Submit week" }).click();
  await expect(page.getByText("Waiting for manager review")).toBeVisible();
  await switchAccount(page, "Monica Hall");
  await expect(page.getByText("Week submitted", { exact: true })).toHaveCount(
    0,
  );
  await navigate(page, "Manager Review");
  await page.getByRole("button", { name: "View Erlich Bachman" }).click();
  await page.getByLabel("Reason for rejection").fill("QA: correct the hours");
  await page.getByRole("button", { name: "Reject request" }).click();
  await expect(page.getByText("You’re all caught up")).toBeVisible();
  await switchAccount(page, "Erlich Bachman");
  await page.getByLabel("Timesheet week").fill("2027-03-01");
  await expect(
    page.getByText("Manager feedback: QA: correct the hours"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "PiperNet on 03/02: 8.25 hours", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Edit QA correction lifecycle", exact: true })
    .click();
  await page.getByLabel("Hours", { exact: true }).fill("7.5");
  await page.getByRole("button", { name: "Save entry" }).click();
  await expect(page.getByText("DRAFT", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Manager feedback: QA: correct the hours"),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Submit week" }).click();
  await expect(page.getByText("Waiting for manager review")).toBeVisible();
  await switchAccount(page, "Monica Hall");
  await navigate(page, "Manager Review");
  await page.getByRole("button", { name: "View Erlich Bachman" }).click();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("You’re all caught up")).toBeVisible();
  await switchAccount(page, "Erlich Bachman");
  await page.getByLabel("Timesheet week").fill("2027-03-01");
  await expect(page.getByText("Reviewed by Monica Hall")).toBeVisible();
  await page
    .getByRole("button", { name: "PiperNet on 03/02: 7.5 hours", exact: true })
    .click();
  await expect(
    page.getByText("This timesheet is locked for review."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Add entry", exact: true }),
  ).toHaveCount(0);
});

test("closed ticket can reopen and an assigned ticket has no ineffective empty assignment", async ({
  page,
}) => {
  await login(page, "Richard Hendricks");
  await navigate(page, "Support Tickets");
  await page.getByRole("button", { name: "New ticket", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("QA ticket reopening");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await page
    .getByRole("button", { name: "View QA ticket reopening", exact: true })
    .click();
  await expect(
    page.getByLabel("Assign ticket").locator('option[value=""]'),
  ).toBeDisabled();
  await page.getByLabel("Assign ticket").selectOption({ label: "Jared Dunn" });
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: "QA ticket reopening" })
      .getByText("Jared Dunn", { exact: true }),
  ).toBeVisible();
  for (const status of ["IN_PROGRESS", "RESOLVED", "CLOSED", "OPEN"]) {
    await page
      .getByRole("button", { name: "View QA ticket reopening", exact: true })
      .click();
    await page.getByLabel("Ticket status").selectOption(status);
    await expect(
      page
        .getByRole("row")
        .filter({ hasText: "QA ticket reopening" })
        .getByText(status.replaceAll("_", " "), { exact: true }),
    ).toBeVisible();
  }
  await navigate(page, "Employee Directory");
  await page.getByLabel("Search records").fill("Richard");
  await expect(
    page.getByText("1 person · Updates every 10 seconds"),
  ).toBeVisible();
  await expect(page.getByRole("columnheader")).toHaveCount(4);
});

test("shared browser sessions synchronize account switches and close stale forms", async ({
  page,
  context,
}) => {
  await login(page, "Dinesh Chugtai");
  await navigate(page, "Support Tickets");
  await page.getByRole("button", { name: "New ticket", exact: true }).click();
  await page
    .getByLabel("Title", { exact: true })
    .fill("This stale form must not be submitted");
  const other = await context.newPage();
  await other.goto("/");
  await expect(
    other.getByRole("button", { name: "Switch account" }),
  ).toBeVisible();
  await switchAccount(other, "Monica Hall");
  await expect(
    page.getByRole("heading", { name: "My Timesheet", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.locator(".topbar").getByText("Monica Hall", { exact: true }),
  ).toBeVisible();
  await navigate(page, "Support Tickets");
  await expect(
    page.getByRole("button", {
      name: "View This stale form must not be submitted",
      exact: true,
    }),
  ).toHaveCount(0);
  await other.getByRole("button", { name: "Switch account" }).click();
  await expect(
    page.getByRole("button", {
      name: "Sign in as Dinesh Chugtai",
      exact: true,
    }),
  ).toBeVisible();
  await other.close();
});

for (const width of [390, 1280]) {
  test(`dialogs are centered at ${width}px and all ticket statuses are visible`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await login(page, "Dinesh Chugtai");
    await page.getByRole("button", { name: "Log time", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(Math.abs(box!.x + box!.width / 2 - width / 2)).toBeLessThan(2);
    expect(Math.abs(box!.y + box!.height / 2 - 844 / 2)).toBeLessThan(2);
    await page.getByRole("button", { name: "Close dialog" }).click();
    if (width === 390)
      await page.getByRole("button", { name: "Open navigation" }).click();
    await navigate(page, "Support Tickets");
    await page
      .getByRole("button", {
        name: "View PiperNet staging VPN disconnects",
        exact: true,
      })
      .click();
    const status = page.getByLabel("Ticket status", { exact: true });
    await expect(status).toHaveValue("IN_PROGRESS");
    await expect(status.locator("option")).toHaveCount(4);
    for (const value of ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"])
      await expect(status.locator('option[value="' + value + '"]')).toBeEnabled();
  });
}

test("Monica can assign a ticket to Dinesh who can see and work on it", async ({
  page,
}) => {
  await login(page, "Monica Hall");
  await navigate(page, "Support Tickets");
  await page.getByRole("button", { name: "New ticket", exact: true }).click();
  await page
    .getByLabel("Title", { exact: true })
    .fill("QA assignee visibility");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await page
    .getByRole("button", { name: "View QA assignee visibility", exact: true })
    .click();
  await page
    .getByLabel("Assign ticket")
    .selectOption({ label: "Dinesh Chugtai" });
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: "QA assignee visibility" })
      .getByText("Dinesh Chugtai", { exact: true }),
  ).toBeVisible();
  await switchAccount(page, "Dinesh Chugtai");
  await navigate(page, "Support Tickets");
  await page
    .getByRole("button", { name: "View QA assignee visibility", exact: true })
    .click();
  await expect(page.getByLabel("Assign ticket")).toHaveCount(0);
  await expect(page.getByLabel("Priority", { exact: true })).toHaveCount(0);
  await page.getByLabel("Ticket status").selectOption("IN_PROGRESS");
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: "QA assignee visibility" })
      .getByText("IN PROGRESS", { exact: true }),
  ).toBeVisible();
  await switchAccount(page, "Jared Dunn");
  await navigate(page, "Support Tickets");
  await expect(
    page.getByRole("button", {
      name: "View QA assignee visibility",
      exact: true,
    }),
  ).toHaveCount(0);
  await switchAccount(page, "Monica Hall");
  await navigate(page, "Support Tickets");
  await page
    .getByRole("button", { name: "View QA assignee visibility", exact: true })
    .click();
  await page.getByLabel("Assign ticket").selectOption({ label: "Jared Dunn" });
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: "QA assignee visibility" })
      .getByText("Jared Dunn", { exact: true }),
  ).toBeVisible();
  await switchAccount(page, "Dinesh Chugtai");
  await navigate(page, "Support Tickets");
  await expect(
    page.getByRole("button", {
      name: "View QA assignee visibility",
      exact: true,
    }),
  ).toHaveCount(0);
});

test("manager leave requires admin review and approval is visible to the requester", async ({
  page,
}) => {
  await login(page, "Monica Hall");
  await navigate(page, "Leave");
  await page
    .getByRole("button", { name: "Request leave", exact: true })
    .click();
  await page.getByLabel("Start date").fill("2027-06-07");
  await page.getByLabel("End date").fill("2027-06-07");
  await page.getByLabel("Reason (optional)").fill("QA admin leave approval");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByRole("row").filter({ hasText: "QA admin leave approval" }),
  ).toBeVisible();
  await navigate(page, "Manager Review");
  await expect(
    page.getByRole("row").filter({ hasText: "QA admin leave approval" }),
  ).toHaveCount(0);
  await switchAccount(page, "Richard Hendricks");
  await navigate(page, "Manager Review");
  await page.getByLabel("Filter request type").selectOption("leave");
  await page
    .getByRole("row")
    .filter({ hasText: "QA admin leave approval" })
    .getByRole("button")
    .click();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(
    page.getByRole("row").filter({ hasText: "QA admin leave approval" }),
  ).toHaveCount(0);
  await switchAccount(page, "Monica Hall");
  await navigate(page, "Leave");
  await page.getByLabel("Filter status").selectOption("APPROVED");
  await page
    .getByRole("row")
    .filter({ hasText: "QA admin leave approval" })
    .getByRole("button")
    .click();
  await expect(
    page.getByText("Reviewed by Richard Hendricks", { exact: true }),
  ).toBeVisible();
});

test("filtered ticket pagination preserves search and displays the remaining record", async ({
  page,
}) => {
  await login(page, "Richard Hendricks");
  // Prepare isolated fixture data through the same REST boundary, then use the UI.
  const identity = await page.request.get("/api/v1/auth/me");
  const csrf = (await identity.json()).csrf_token;
  for (let index = 0; index < 51; index++) {
    const response = await page.request.post("/api/v1/tickets", {
      headers: { Origin: "http://localhost:3010", "X-CSRF-Token": csrf },
      data: { title: `Pagination QA ${index}` },
    });
    expect(response.ok()).toBeTruthy();
  }
  await navigate(page, "Support Tickets");
  await page.getByLabel("Search records").fill("Pagination QA");
  await expect(
    page.getByText("51 records · Updates every 10 seconds"),
  ).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(51);
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(page.getByRole("row")).toHaveCount(2);
  await expect(
    page.getByRole("button", { name: "View Pagination QA 0", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Search records")).toHaveValue("Pagination QA");
  await expect(
    page.getByRole("button", { name: "Next page", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Previous page", exact: true })
    .click();
  await expect(page.getByRole("row")).toHaveCount(51);
});

test("ticket creator can skip directly to resolved or closed and reopen", async ({ page }) => {
  await login(page, "Dinesh Chugtai");
  await navigate(page, "Support Tickets");
  await page.getByRole("button", { name: "New ticket", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("QA unrestricted status");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  for (const status of ["RESOLVED", "OPEN", "CLOSED", "IN_PROGRESS"]) {
    await page.getByRole("button", { name: "View QA unrestricted status", exact: true }).click();
    await expect(page.getByLabel("Assign ticket")).toHaveCount(0);
    await expect(page.getByLabel("Priority", { exact: true })).toHaveCount(0);
    await page.getByLabel("Ticket status").selectOption(status);
    await expect(page.getByRole("row").filter({ hasText: "QA unrestricted status" })
      .getByText(status.replaceAll("_", " "), { exact: true })).toBeVisible();
  }
  await navigate(page, "Activity");
  await expect(page.getByText("update_ticket_status", { exact: true }).first()).toBeVisible();
});
