import { runTest } from "./auth";

runTest("Demo Test", async helper => {
  const { page } = helper;

  console.log("📍 Testing /dashboard route...");
  await helper.goto("/dashboard");

  await helper.screenshot("demo-dashboard.png");

  const hasWelcome = await page
    .locator("text=Welcome")
    .isVisible()
    .catch(() => false);
  const isOnDashboard = page.url().includes("/dashboard");

  console.log(`   ✓ Welcome message: ${hasWelcome}`);
  console.log(`   ✓ On dashboard: ${isOnDashboard}`);
  console.log(`   ✓ URL: ${page.url()}`);

  if (!hasWelcome || !isOnDashboard) {
    throw new Error("Dashboard not working");
  }

  console.log("\n📍 Testing /settings route...");
  await helper.goto("/settings");
  await page
    .waitForSelector("text=Settings", { timeout: 5000 })
    .catch(() => {});
  await helper.screenshot("demo-settings.png");

  const pageContent = await page.locator("body").innerText();
  const hasSettings = pageContent.includes("Settings");
  console.log(`   ✓ Settings visible: ${hasSettings}`);
  console.log(`   ✓ URL: ${page.url()}`);

  if (!hasSettings) {
    throw new Error("Settings page not working");
  }

  console.log("\n📍 Testing landing page...");
  await helper.goto("/");
  await helper.screenshot("demo-landing.png");
  const landingContent = await page.locator("body").innerText();
  const hasLanding =
    landingContent.includes("Main Headline") ||
    landingContent.includes("Get Started");
  console.log(`   ✓ Landing page content: ${hasLanding}`);
  console.log(`   ✓ URL: ${page.url()}`);

  if (!hasLanding) {
    throw new Error("Landing page not working");
  }

  console.log("\n🎉 All routes working!");
}).catch(() => process.exit(1));
