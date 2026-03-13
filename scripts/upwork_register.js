const { chromium } = require('playwright');

// === Ying's Profile Data ===
const PROFILE = {
  firstName: 'Kris',
  // lastName needs to be filled - script will pause for this
  email: 'xmqywx@gmail.com',
  country: 'China',

  title: 'AI Agent Developer | Claude/GPT Integration | Shopify AI Solutions | Full-Stack',

  overview: `I build AI-powered systems that solve real business problems — not toy demos.

What I deliver:
• Custom AI agents and chatbots (Claude API, OpenAI, LangChain, LangGraph)
• Shopify AI integration — product recommendations, customer support bots, automated workflows
• RAG systems with vector search (pgvector, Pinecone, ChromaDB)
• Full-stack web applications (React, Next.js, Node.js, Python/FastAPI, Go)
• Automation workflows (n8n, Make, custom pipelines)

Recent work:
• Built YepAI: an AI SaaS platform with Shopify integration, HubSpot CRM sync, and intelligent chatbot — serving live customers
• Developed a quantitative trading system with 5 automated strategies, backtesting framework, and web dashboard
• Created AI-powered product selection engine with pgvector embeddings, PPT auto-generation, and AI copywriting for cross-border e-commerce
• Built multi-agent AI assistant system running 24/7 on dedicated hardware with memory, scheduling, and proactive task execution

Tech stack: Python, TypeScript, React, Next.js, Node.js, Go, Java, FastAPI, PostgreSQL, Redis, Docker, AWS, Shopify API, Claude API, OpenAI API, LangChain, pgvector

Why work with me:
• I ship fast. Full-stack means no hand-offs, no delays.
• 7+ years building production systems across web, mobile, backend, and AI.
• I understand both the tech AND the business problem.
• Available for long-term collaboration and retainer arrangements.`,

  skills: [
    'Artificial Intelligence',
    'AI Agent Development',
    'Python',
    'TypeScript',
    'React',
    'Node.js',
    'Shopify Development',
    'Chatbot Development',
    'OpenAI API',
    'LangChain',
    'FastAPI',
    'PostgreSQL',
    'Docker',
    'Full-Stack Development',
    'Automation'
  ],

  hourlyRate: 40,
};

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForUserAction(page, message) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`⏸️  需要你操作: ${message}`);
  console.log(`   完成后按 Enter 继续...`);
  console.log(`${'='.repeat(60)}\n`);

  // Wait for user to press Enter in terminal
  await new Promise(resolve => {
    process.stdin.resume();
    process.stdin.once('data', () => {
      process.stdin.pause();
      resolve();
    });
  });
}

async function main() {
  console.log('🚀 启动 Upwork 注册自动化...\n');

  // Launch visible browser (use system Chrome)
  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome',
    args: ['--start-maximized'],
  });

  const context = await browser.newContext({
    viewport: null, // maximize
    locale: 'en-US',
    timezoneId: 'Asia/Shanghai',
  });

  const page = await context.newPage();

  try {
    // Step 1: Navigate to signup
    console.log('📍 打开 Upwork 注册页面...');
    await page.goto('https://www.upwork.com/nx/signup/?dest=home', {
      waitUntil: 'networkidle',
      timeout: 30000
    });
    await sleep(2000);

    // Try to find and click "Work as a freelancer" or similar
    console.log('📍 选择 Freelancer 账户类型...');

    // Look for freelancer option - Upwork may show different flows
    const freelancerBtn = page.locator('text=/freelancer/i').first();
    if (await freelancerBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await freelancerBtn.click();
      await sleep(1000);
    }

    // Try to find "Apply as a Freelancer" or "I'm a freelancer" button
    const applyBtn = page.locator('[data-qa="btn-apply"], button:has-text("freelancer"), a:has-text("freelancer")').first();
    if (await applyBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await applyBtn.click();
      await sleep(2000);
    }

    // Step 2: Fill registration form
    console.log('📝 填写注册信息...');

    // Try various selectors for the signup form fields
    const selectors = {
      firstName: [
        '#first-name',
        'input[name="firstName"]',
        'input[placeholder*="First"]',
        '[data-qa="first-name"]',
        'input[id*="first"]'
      ],
      lastName: [
        '#last-name',
        'input[name="lastName"]',
        'input[placeholder*="Last"]',
        '[data-qa="last-name"]',
        'input[id*="last"]'
      ],
      email: [
        '#email',
        'input[name="email"]',
        'input[type="email"]',
        'input[placeholder*="Email"]',
        '[data-qa="email"]'
      ],
      password: [
        '#password',
        'input[name="password"]',
        'input[type="password"]',
        '[data-qa="password"]'
      ],
    };

    async function tryFill(fieldSelectors, value, fieldName) {
      for (const sel of fieldSelectors) {
        try {
          const el = page.locator(sel).first();
          if (await el.isVisible({ timeout: 2000 })) {
            await el.clear();
            await el.fill(value);
            console.log(`  ✅ ${fieldName} 已填写`);
            return true;
          }
        } catch (e) {}
      }
      console.log(`  ⚠️ ${fieldName} 未找到输入框，可能在下一步`);
      return false;
    }

    // Fill first name
    await tryFill(selectors.firstName, PROFILE.firstName, 'First Name');

    // For last name - pause and ask
    await waitForUserAction(page, '请在浏览器中输入你的 Last Name (姓的拼音)，然后回来按 Enter');

    // Fill email
    await tryFill(selectors.email, PROFILE.email, 'Email');

    // Generate a strong password
    const password = 'Kris' + Math.random().toString(36).slice(2, 8) + '!2026';
    const filled = await tryFill(selectors.password, password, 'Password');
    if (filled) {
      console.log(`  🔑 生成的密码: ${password}`);
      console.log(`  ⚠️  请记住这个密码！`);
    }

    // Look for country selector
    const countrySelectors = [
      'select[name="country"]',
      '[data-qa="country"]',
      '#country',
      'input[placeholder*="Country"]'
    ];
    for (const sel of countrySelectors) {
      try {
        const el = page.locator(sel).first();
        if (await el.isVisible({ timeout: 2000 })) {
          if (await el.evaluate(e => e.tagName) === 'SELECT') {
            await el.selectOption({ label: 'China' });
          } else {
            await el.fill('China');
          }
          console.log('  ✅ Country 已选择: China');
          break;
        }
      } catch (e) {}
    }

    // Look for terms checkbox
    const termsCheckbox = page.locator('input[type="checkbox"]').first();
    if (await termsCheckbox.isVisible({ timeout: 2000 }).catch(() => false)) {
      await termsCheckbox.check();
      console.log('  ✅ 已勾选条款');
    }

    // Handle CAPTCHA and submit
    await waitForUserAction(page, '请完成以下操作:\n   1. 检查表单信息是否正确\n   2. 如果有 CAPTCHA，请完成验证\n   3. 点击 "Create my account" 或 "Sign Up" 按钮\n   4. 然后回来按 Enter');

    // Step 3: Email verification
    await waitForUserAction(page, '请去邮箱 xmqywx@gmail.com 点击验证链接，完成后回来按 Enter');

    // Step 4: Profile setup - try to fill title and overview
    console.log('\n📝 填写 Profile 信息...');
    await sleep(3000);

    // Professional title
    const titleSelectors = [
      'input[placeholder*="title"]',
      'input[name="title"]',
      '[data-qa="title"]',
      '#title',
      'input[placeholder*="headline"]'
    ];
    await tryFill(titleSelectors, PROFILE.title, 'Professional Title');

    // Overview/bio
    const overviewSelectors = [
      'textarea[name="overview"]',
      'textarea[placeholder*="overview"]',
      '[data-qa="overview"]',
      '#overview',
      'textarea'
    ];
    for (const sel of overviewSelectors) {
      try {
        const el = page.locator(sel).first();
        if (await el.isVisible({ timeout: 2000 })) {
          await el.clear();
          await el.fill(PROFILE.overview);
          console.log('  ✅ Overview 已填写');
          break;
        }
      } catch (e) {}
    }

    // Hourly rate
    const rateSelectors = [
      'input[name="rate"]',
      'input[placeholder*="rate"]',
      'input[placeholder*="hour"]',
      '[data-qa="rate"]'
    ];
    await tryFill(rateSelectors, String(PROFILE.hourlyRate), 'Hourly Rate ($40)');

    // Skills - try to add them
    console.log('\n📍 添加技能标签...');
    const skillInput = page.locator('input[placeholder*="skill"], input[placeholder*="Skill"], [data-qa="skill-input"]').first();
    if (await skillInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      for (const skill of PROFILE.skills) {
        try {
          await skillInput.clear();
          await skillInput.fill(skill);
          await sleep(500);
          // Try to select from dropdown
          const suggestion = page.locator(`text="${skill}"`).first();
          if (await suggestion.isVisible({ timeout: 1000 }).catch(() => false)) {
            await suggestion.click();
          } else {
            await skillInput.press('Enter');
          }
          await sleep(300);
          console.log(`  ✅ 已添加技能: ${skill}`);
        } catch (e) {
          console.log(`  ⚠️ 添加技能失败: ${skill}`);
        }
      }
    } else {
      console.log('  ⚠️ 技能输入框未找到，可能在其他步骤');
    }

    // Final steps
    await waitForUserAction(page, '请完成剩余的 Profile 设置步骤（如有），包括:\n   - 上传头像照片\n   - 选择专业领域\n   - 手机号验证 (如需要)\n   - 提交 Profile 审核\n   完成后按 Enter');

    console.log('\n✅ Upwork 注册流程完成！');
    console.log('\n📋 账户信息:');
    console.log(`   Email: ${PROFILE.email}`);
    if (filled) console.log(`   Password: ${password}`);
    console.log(`   Hourly Rate: $${PROFILE.hourlyRate}/hr`);
    console.log('\n💡 提示: Profile 提交后通常 24-72 小时内审批');
    console.log('   审批通过后就可以开始投标了！\n');

    // Keep browser open
    await waitForUserAction(page, '按 Enter 关闭浏览器');

  } catch (error) {
    console.error('❌ 出错了:', error.message);
    await waitForUserAction(page, '出现错误，请手动完成注册。按 Enter 关闭浏览器');
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
