import { expect, test, type Page } from "@playwright/test";

// One request, all the way from intake to done, as four different people.
// Set SCREENSHOTS=1 to also save a picture of each step into docs/screenshots.

const SHOTS = process.env.SCREENSHOTS ? "../docs/screenshots" : null;

async function actAs(page: Page, name: string) {
  await page.getByLabel("Acting as").selectOption({ label: name });
}

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` });
}

// Rows are found by the request's id (from its link), so earlier runs against
// the same database don't get in the way.
function rowsFor(page: Page, id: string) {
  return page.locator(`tbody tr:has(a[href="/requests/${id}"])`);
}

test("a request goes from intake to done, with an audit trail", async ({ page }) => {
  const title = "Access to the finance dashboard";
  let id = "";

  await test.step("Asha raises a request", async () => {
    await page.goto("/");
    await actAs(page, "Asha (Requester)");
    await page.getByLabel("Title").fill(title);
    await page.getByLabel("Category").selectOption("access");
    await page.getByLabel("Details").fill("Read-only access is enough. I need it for the quarterly review.");
    await page.getByRole("button", { name: "Submit request" }).click();
    await expect(page.getByRole("status")).toContainText("created");
    id = (await page.getByRole("status").innerText()).match(/#(\d+)/)![1];
    const row = rowsFor(page, id);
    await expect(row).toContainText(title);
    await expect(row).toContainText("New");
    await shot(page, "1-raised");
    await row.getByRole("link", { name: title }).click();
    await expect(page).toHaveURL(`/requests/${id}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
    await expect(page.getByText("Nothing for Asha to do here right now.")).toBeVisible();
  });

  await test.step("Ravi on the service desk triages it", async () => {
    await actAs(page, "Ravi (Service desk)");
    await page.getByLabel("Priority").selectOption("high");
    await page.getByLabel("Note (optional)").fill("Finance asked for it");
    await page.getByRole("button", { name: "Triage" }).click();
    await expect(page.locator(".badge").first()).toHaveText("Triaged");
    // Ravi can't approve: the button isn't there for him.
    await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
  });

  await test.step("Meera approves it, and who and when are recorded", async () => {
    await actAs(page, "Meera (Approver)");
    await page.getByLabel("Note (needed to reject)").fill("Fine for one quarter");
    await shot(page, "2-waiting-for-approval");
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.locator(".badge").first()).toHaveText("Approved");
    await expect(page.getByTestId("decision")).toContainText("Approved by Meera on");
  });

  await test.step("Ravi does the work and marks it done", async () => {
    await actAs(page, "Ravi (Service desk)");
    await page.getByLabel("What was done").fill("Granted read-only access to the finance dashboard");
    await page.getByRole("button", { name: "Mark done" }).click();
    await expect(page.locator(".badge").first()).toHaveText("Done");
    await expect(page.getByText("Done. Nothing left to do.")).toBeVisible();
    await shot(page, "3-done-with-history");
  });

  await test.step("The audit log shows every step, in order", async () => {
    await page.getByRole("link", { name: "Audit log" }).click();
    const rows = rowsFor(page, id);
    await expect(rows).toHaveCount(4);
    // Newest first.
    await expect(rows.nth(0)).toContainText("Ravi");
    await expect(rows.nth(0)).toContainText("marked it done");
    await expect(rows.nth(1)).toContainText("Meera");
    await expect(rows.nth(1)).toContainText("approved it");
    await expect(rows.nth(2)).toContainText("triaged it");
    await expect(rows.nth(3)).toContainText("raised it");
    await shot(page, "4-audit-log");
  });
});

test("the server refuses a step the page doesn't offer", async ({ request }) => {
  // The buttons are only a convenience. The API enforces the rules itself.
  const created = await request.post("/api/requests", {
    headers: { "X-Acting-As": "asha" },
    data: { title: "New laptop", category: "hardware" },
  });
  const { id } = await created.json();
  const approve = await request.post(`/api/requests/${id}/approve`, {
    headers: { "X-Acting-As": "asha" },
    data: {},
  });
  expect(approve.status()).toBe(403);
  expect((await approve.json()).detail).toBe(
    "Asha is a requester and can't approve requests. An approver has to do it.",
  );
});
