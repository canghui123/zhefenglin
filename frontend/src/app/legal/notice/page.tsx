import Link from "next/link";

export const metadata = {
  title: "服务使用须知 | 汽车金融资产处置经营决策系统",
};

// 上线前请将以下占位符替换为真实主体信息：
//   COMPANY_NAME        —— 公司全称
//   CREDIT_CODE         —— 统一社会信用代码
//   COMPANY_ADDRESS     —— 注册地址
//   CONTACT_EMAIL       —— 数据相关问题专用邮箱（建议 dpo@ 域名）
//   CONTACT_PHONE       —— 联系电话
//   LAST_UPDATED        —— 本文本最后修改日期
const COMPANY_NAME = "【请在上线前填入公司全称】";
const CREDIT_CODE = "【请在上线前填入统一社会信用代码】";
const COMPANY_ADDRESS = "【请在上线前填入注册地址】";
const CONTACT_EMAIL = "dpo@zhefenglin.com";
const CONTACT_PHONE = "【请在上线前填入联系电话】";
const LAST_UPDATED = "2026-04-21";

export default function LegalNoticePage() {
  return (
    <article className="prose prose-slate max-w-3xl mx-auto py-8 space-y-4 text-sm leading-7">
      <h1 className="text-2xl font-semibold">服务使用须知</h1>

      <p className="text-muted-foreground">
        最后更新：{LAST_UPDATED}
      </p>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">一、主体信息</h2>
        <ul className="list-disc pl-6 space-y-1">
          <li>运营主体：{COMPANY_NAME}</li>
          <li>统一社会信用代码：{CREDIT_CODE}</li>
          <li>注册地址：{COMPANY_ADDRESS}</li>
          <li>
            联系邮箱：
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary hover:underline">
              {CONTACT_EMAIL}
            </a>
          </li>
          <li>联系电话：{CONTACT_PHONE}</li>
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">二、服务性质</h2>
        <p>
          本平台（下称&quot;本服务&quot;）为汽车金融不良资产定价与库存决策辅助工具，
          <strong>仅向受邀企业用户提供内测服务</strong>，不面向自然人个人用户，不面向未满
          18 周岁用户。
        </p>
        <p>
          本服务提供的资产定价、贬值预测、处置路径建议等输出，均基于算法和市场
          数据的估算，
          <strong>仅供用户内部决策参考，不构成交易承诺、投资建议或任何法律意见</strong>
          。最终决策权归用户所有，由此产生的一切结果由用户自行承担。
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">三、数据处理</h2>
        <p>
          用户上传的资产包文件、车辆信息、处置参数等数据存储在
          <strong>中国大陆境内</strong>（阿里云华东/华北节点），不跨境传输。
        </p>
        <p>
          我们<strong>不主动收集</strong>资产包中债务人个人信息。若用户上传的
          资产包中包含此类信息：
        </p>
        <ul className="list-disc pl-6 space-y-1">
          <li>
            数据控制者为上传该资产包的企业用户，本平台作为受托处理者按用户指示处理；
          </li>
          <li>本平台不会将此类信息用于除本服务外的任何用途；</li>
          <li>不会共享、出售、披露给任何第三方；</li>
          <li>不会用于 AI 模型训练或画像。</li>
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">四、第三方服务</h2>
        <p>
          为向您提供服务，本平台调用以下第三方接口，相关数据处理遵循各自的隐私政策：
        </p>
        <ul className="list-disc pl-6 space-y-1">
          <li>阿里云（云服务器、对象存储、数据库）</li>
          <li>车300（车辆估值 API）</li>
          <li>DeepSeek / 通义千问（大语言模型推理）</li>
          <li>Let&apos;s Encrypt（SSL 证书）</li>
        </ul>
        <p>
          若子处理者发生变更，我们将在官网及本页面予以 10 天前书面公告。
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">五、数据保留与删除</h2>
        <ul className="list-disc pl-6 space-y-1">
          <li>账号数据保留期：服务期内 + 终止后 30 日</li>
          <li>历史备份保留期：180 日，到期自动销毁</li>
          <li>审计日志保留期：6 个月</li>
          <li>
            如需删除账号和全部数据，发送邮件至
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary hover:underline mx-1">
              {CONTACT_EMAIL}
            </a>
            ，我们将在 7 个工作日内处理并提供删除确认。
          </li>
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">六、自动化决策告知</h2>
        <p>
          本平台采用算法对用户上传的资产包生成定价建议和决策报告，
          属于《个人信息保护法》第二十四条所称的自动化决策。用户有权：
        </p>
        <ul className="list-disc pl-6 space-y-1">
          <li>要求对算法输出结果进行人工复核；</li>
          <li>要求我们说明算法输入与关键参数；</li>
          <li>拒绝仅通过自动化决策做出对其有重大影响的决定。</li>
        </ul>
        <p>
          行使上述权利请邮件至
          <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary hover:underline mx-1">
            {CONTACT_EMAIL}
          </a>
          ，7 个工作日内回复。
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">七、用户禁止行为</h2>
        <ul className="list-disc pl-6 space-y-1">
          <li>上传与车辆处置业务无关的数据；</li>
          <li>
            上传涉及个人敏感信息（身份证号、银行卡号、住址、行踪轨迹等）而未向
            对应主体取得单独授权的数据；
          </li>
          <li>利用本平台进行暴力催收、非法定位车辆、非法采集个人信息；</li>
          <li>对平台进行扫描、渗透、爬取、逆向工程；</li>
          <li>将账号转让、出借、多人共用。</li>
        </ul>
        <p>
          如发现上述行为，本平台有权立即封禁账号并保留追究法律责任的权利。
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">八、争议解决与变更</h2>
        <p>
          本须知适用中华人民共和国法律。若发生争议，双方协商不成的，提交
          {COMPANY_ADDRESS} 所在地仲裁委员会仲裁。
        </p>
        <p>
          本须知可能根据监管要求或服务迭代进行更新。重大变更将通过站内公告或邮件
          事先通知。继续使用服务即视为接受更新版本。
        </p>
      </section>

      <div className="pt-4 border-t text-muted-foreground">
        <Link href="/register" className="text-primary hover:underline">
          ← 返回注册申请页
        </Link>
      </div>
    </article>
  );
}
