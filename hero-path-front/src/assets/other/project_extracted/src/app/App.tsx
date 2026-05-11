import svgPaths from "../imports/Shop/svg-hnfsiyqngr";
import img261 from "figma:asset/f47a03b8dc82ad15045ccd0c7df28f719cccfb01.png";
import imgEllipse22 from "figma:asset/45efabb9145b05ed239cc7def9c817c85a12c14d.png";
import imgRectangle551 from "figma:asset/9fec63bfcaa52547a5976965361456af0f3fffc3.png";
import { useState } from "react";

// ── Sidebar nav icons ──────────────────────────────────────────────────────

function IconHome({ active }: { active?: boolean }) {
  const c = active ? "#F5F5F5" : "#9A33F4";
  return (
    <svg className="block size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 29.9069 28.0512">
      <path d={svgPaths.p1478a600} fill={c} />
    </svg>
  );
}

function IconProfile({ active }: { active?: boolean }) {
  const c = active ? "#F5F5F5" : "#9A33F4";
  return (
    <svg className="block size-full" fill="none" viewBox="0 0 48 48">
      <ellipse cx="24" cy="17" rx="7" ry="7" fill={c} />
      <path d={svgPaths.p2d558400} fill={c} transform="translate(11, 31) scale(0.95)" />
    </svg>
  );
}

function IconQuests({ active }: { active?: boolean }) {
  const c = active ? "#F5F5F5" : "#9A33F4";
  return (
    <svg className="block size-full" fill="none" viewBox="0 0 32 29">
      <rect fill={c} height="5" rx="2.5" width="22" x="10" y="1" />
      <rect fill={c} height="5" rx="2.5" width="22" x="10" y="12" />
      <rect fill={c} height="5" rx="2.5" width="22" x="10" y="23" />
      <circle cx="3.5" cy="3.5" fill={c} r="3.5" />
      <circle cx="3.5" cy="14.5" fill={c} r="3.5" />
      <circle cx="3.5" cy="25.5" fill={c} r="3.5" />
    </svg>
  );
}

function IconShop({ active }: { active?: boolean }) {
  const c = active ? "#F5F5F5" : "#9A33F4";
  return (
    <svg className="block size-full" fill="none" viewBox="0 0 48 48">
      <path d={svgPaths.p1d441d00} fill={c} transform="translate(9, 9)" />
      <circle cx="20" cy="39" r="4" fill={c} />
      <circle cx="36" cy="39" r="4" fill={c} />
    </svg>
  );
}

function IconLeaders({ active }: { active?: boolean }) {
  const c = active ? "#F5F5F5" : "#9A33F4";
  return (
    <svg className="block size-full" fill="none" viewBox="0 0 31.696 24.7595">
      <path d={svgPaths.p18cb9a80} fill={c} />
    </svg>
  );
}

function IconSquads({ active }: { active?: boolean }) {
  const c = active ? "#F5F5F5" : "#9A33F4";
  return (
    <svg className="block size-full" fill="none" viewBox="0 0 48 48">
      <circle cx="16" cy="17" r="7" fill={c} />
      <circle cx="32" cy="17" r="7" fill={c} />
      <path d={svgPaths.p5059000} fill={c} transform="translate(2, 32)" />
      <path d={svgPaths.p5059000} fill={c} transform="translate(18, 32)" />
    </svg>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────

const navItems = [
  { id: "home", label: "Главная", Icon: IconHome },
  { id: "profile", label: "Профиль", Icon: IconProfile },
  { id: "quests", label: "Квесты", Icon: IconQuests },
  { id: "shop", label: "Магазин", Icon: IconShop },
  { id: "leaders", label: "Лидеры", Icon: IconLeaders },
  { id: "squads", label: "Отряды", Icon: IconSquads },
];

function Sidebar({ activeNav }: { activeNav: string }) {
  return (
    <div
      className="flex flex-col items-center gap-5 py-6 rounded-3xl overflow-hidden"
      style={{
        width: 100,
        background: "#F5F5F5",
        boxShadow: "25px 25px 20px -20px rgba(0,0,0,0.45)",
        flexShrink: 0,
      }}
    >
      {navItems.map(({ id, label, Icon }) => {
        const isActive = activeNav === id;
        return (
          <div key={id} className="flex flex-col items-center w-full">
            <div
              className="flex items-center justify-center w-full"
              style={{
                height: 52,
                background: isActive
                  ? "linear-gradient(to left, rgba(90,30,142,0), rgba(154,51,244,0.69), rgba(90,30,142,0))"
                  : "transparent",
              }}
            >
              <div style={{ width: 32, height: 32 }}>
                <Icon active={isActive} />
              </div>
            </div>
            <span
              style={{
                fontFamily: "'Montserrat', sans-serif",
                fontWeight: 600,
                fontSize: 14,
                color: isActive ? "#9A33F4" : "#9A33F4",
                textAlign: "center",
                lineHeight: 1.2,
              }}
            >
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Header ─────────────────────────────────────────────────────────────────

function Header() {
  return (
    <div
      className="flex items-center justify-between px-4 relative overflow-hidden"
      style={{
        background: "#9A33F4",
        borderRadius: 24,
        height: 82,
        boxShadow: "25px 25px 20px -20px rgba(0,0,0,0.45)",
      }}
    >
      {/* Logo + Title */}
      <div className="flex items-center gap-1">
        <div style={{ width: 167, height: 60, flexShrink: 0, position: "relative", overflow: "hidden" }}>
          <img
            alt="IThub logo"
            src={img261}
            style={{ position: "absolute", height: "105%", top: "-5%", left: "1.62%", width: "98.56%", maxWidth: "none" }}
          />
        </div>
        <span
          style={{
            fontFamily: "'TT Firs Neue', sans-serif",
            fontWeight: 700,
            fontSize: 28,
            color: "#F5F5F5",
            whiteSpace: "nowrap",
          }}
        >
          Путь героя
        </span>
      </div>

      {/* User info */}
      <div className="flex items-center gap-3">
        <div className="flex flex-wrap items-center justify-end gap-x-1" style={{ width: 218 }}>
          <span
            style={{
              fontFamily: "'Montserrat', sans-serif",
              fontWeight: 600,
              fontSize: 22,
              color: "#FFFFFF",
              whiteSpace: "nowrap",
              width: "100%",
              textAlign: "right",
            }}
          >
            Имя пользователя
          </span>
          <span
            style={{
              fontFamily: "'Montserrat', sans-serif",
              fontWeight: 500,
              fontSize: 20,
              color: "#FFD900",
              whiteSpace: "nowrap",
            }}
          >
            Money:
          </span>
          <span
            style={{
              fontFamily: "'Montserrat', sans-serif",
              fontWeight: 600,
              fontSize: 20,
              color: "#FFD900",
              whiteSpace: "nowrap",
            }}
          >
            9.99
          </span>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="9" fill="#FFD900" />
          </svg>
        </div>
        <img alt="Avatar" src={imgEllipse22} style={{ width: 48, height: 48, borderRadius: "50%" }} />
      </div>
    </div>
  );
}

// ── Tabs ───────────────────────────────────────────────────────────────────

const tabs = ["Кастомизация", "Привелегии", "Мерч", "Статусные"];

function ShopTabs({ active, onSelect }: { active: string; onSelect: (t: string) => void }) {
  return (
    <div
      className="flex items-end gap-6 px-5 relative overflow-hidden"
      style={{
        background: "#F5F5F5",
        borderRadius: 24,
        height: 93,
        boxShadow: "25px 25px 20px -20px rgba(0,0,0,0.45)",
        flexShrink: 0,
      }}
    >
      {tabs.map((tab) => {
        const isActive = active === tab;
        return (
          <div key={tab} className="flex flex-col items-center gap-1 pb-3 cursor-pointer" onClick={() => onSelect(tab)}>
            <span
              style={{
                fontFamily: "'Montserrat', sans-serif",
                fontWeight: isActive ? 700 : 600,
                fontSize: isActive ? 24 : 22,
                color: isActive ? "#9A33F4" : "#848484",
                whiteSpace: "nowrap",
              }}
            >
              {tab}
            </span>
            {isActive && (
              <div
                style={{
                  width: "100%",
                  height: 4,
                  borderRadius: 2,
                  background: "#9A33F4",
                  boxShadow: "5px 5px 17px 2px rgba(154,51,244,0.6)",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Product Card ───────────────────────────────────────────────────────────

function ProductCard({ name, price }: { name: string; price: string }) {
  return (
    <div
      className="flex flex-col gap-3 overflow-hidden"
      style={{
        background: "#F5F5F5",
        borderRadius: 16,
        padding: 12,
        boxShadow: "25px 25px 20px -20px rgba(0,0,0,0.45)",
        flex: "1 1 0",
        minWidth: 0,
      }}
    >
      {/* Image */}
      <div style={{ borderRadius: 12, overflow: "hidden", height: 130, position: "relative", flexShrink: 0 }}>
        <img
          alt={name}
          src={imgRectangle551}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>

      {/* Name + Price */}
      <div className="flex flex-col gap-2">
        <span
          style={{
            fontFamily: "'TT Firs Neue', sans-serif",
            fontWeight: 700,
            fontSize: 20,
            color: "#9A33F4",
          }}
        >
          {name}
        </span>
        <div
          className="flex items-center justify-center gap-2"
          style={{
            background: "#121212",
            borderRadius: 12,
            padding: "6px 12px",
            height: 44,
          }}
        >
          <svg width="22" height="22" viewBox="0 0 26 26" fill="none">
            <circle cx="13" cy="13" r="13" fill="#FFD900" />
          </svg>
          <span
            style={{
              fontFamily: "'TT Firs Neue', sans-serif",
              fontWeight: 700,
              fontSize: 22,
              color: "#FFD900",
              whiteSpace: "nowrap",
            }}
          >
            {price}
          </span>
        </div>
      </div>

      {/* Buy button */}
      <button
        className="relative cursor-pointer"
        style={{
          background: "#9A33F4",
          borderRadius: 16,
          height: 52,
          border: "none",
          outline: "none",
          width: "100%",
          flexShrink: 0,
        }}
      >
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            border: "3px solid #F5F5F5",
            borderRadius: 16,
            pointerEvents: "none",
            boxShadow: "25px 25px 20px -20px rgba(0,0,0,0.45)",
          }}
        />
        <span
          style={{
            fontFamily: "'Montserrat', sans-serif",
            fontWeight: 700,
            fontSize: 20,
            color: "#F5F5F5",
          }}
        >
          Купить
        </span>
      </button>
    </div>
  );
}

// ── Coins Block ────────────────────────────────────────────────────────────

function CoinsBlock() {
  return (
    <div
      className="flex flex-col gap-3"
      style={{
        background: "#9A33F4",
        borderRadius: 24,
        padding: 20,
        boxShadow: "25px 25px 20px -20px rgba(0,0,0,0.45)",
        width: 280,
        flexShrink: 0,
        alignSelf: "flex-start",
      }}
    >
      <p
        style={{
          fontFamily: "'TT Firs Neue', sans-serif",
          fontWeight: 700,
          fontSize: 22,
          color: "#F5F5F5",
          lineHeight: 1.3,
          margin: 0,
        }}
      >
        Сколько монет у пользователя:
      </p>
      <div
        className="flex items-center gap-2"
        style={{
          background: "#121212",
          borderRadius: 12,
          padding: "8px 16px",
          alignSelf: "flex-start",
        }}
      >
        <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
          <circle cx="13" cy="13" r="13" fill="#FFD900" />
        </svg>
        <span
          style={{
            fontFamily: "'TT Firs Neue', sans-serif",
            fontWeight: 700,
            fontSize: 28,
            color: "#FFD900",
            whiteSpace: "nowrap",
          }}
        >
          9.99
        </span>
      </div>
      <button
        className="relative cursor-pointer"
        style={{
          background: "#121212",
          borderRadius: 48,
          height: 48,
          border: "none",
          outline: "none",
          width: "100%",
        }}
      >
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            border: "4px solid #F5F5F5",
            borderRadius: 48,
            pointerEvents: "none",
            boxShadow: "25px 25px 20px -20px rgba(0,0,0,0.83)",
          }}
        />
        <span
          style={{
            fontFamily: "'Montserrat', sans-serif",
            fontWeight: 700,
            fontSize: 20,
            color: "#F5F5F5",
            whiteSpace: "nowrap",
          }}
        >
          История покупок
        </span>
      </button>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────

const products = Array.from({ length: 9 }, (_, i) => ({
  id: i + 1,
  name: "Название",
  price: "9.99",
}));

export default function App() {
  const [activeTab, setActiveTab] = useState("Кастомизация");

  return (
    <div
      className="min-h-screen w-full"
      style={{ background: "#F5F5F5", fontFamily: "'Montserrat', sans-serif" }}
    >
      <div className="mx-auto" style={{ maxWidth: 1200, padding: "26px 20px 40px" }}>
        {/* Header */}
        <Header />

        {/* Body */}
        <div className="flex gap-4 mt-4">
          {/* Sidebar */}
          <Sidebar activeNav="shop" />

          {/* Main */}
          <div className="flex flex-col gap-4 flex-1 min-w-0">
            {/* Top row: tabs + coins block */}
            <div className="flex gap-4 items-start">
              <div className="flex flex-col gap-3 flex-1 min-w-0">
                {/* Tabs */}
                <ShopTabs active={activeTab} onSelect={setActiveTab} />

                {/* My purchases button */}
                <div>
                  <button
                    className="relative cursor-pointer"
                    style={{
                      background: "#F5F5F5",
                      borderRadius: 16,
                      height: 52,
                      padding: "0 24px",
                      border: "none",
                      outline: "none",
                    }}
                  >
                    <div
                      aria-hidden="true"
                      style={{
                        position: "absolute",
                        inset: 0,
                        border: "3px solid #9A33F4",
                        borderRadius: 16,
                        pointerEvents: "none",
                        boxShadow: "25px 25px 20px -20px rgba(0,0,0,0.45)",
                      }}
                    />
                    <span
                      style={{
                        fontFamily: "'Montserrat', sans-serif",
                        fontWeight: 600,
                        fontSize: 18,
                        color: "#9A33F4",
                        whiteSpace: "nowrap",
                        position: "relative",
                      }}
                    >
                      Мои покупки
                    </span>
                  </button>
                </div>
              </div>

              {/* Coins block */}
              <CoinsBlock />
            </div>

            {/* Product grid */}
            <div
              className="grid gap-4"
              style={{ gridTemplateColumns: "repeat(3, 1fr)" }}
            >
              {products.map((p) => (
                <ProductCard key={p.id} name={p.name} price={p.price} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
