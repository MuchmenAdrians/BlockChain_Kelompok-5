"""
ConcertChain - Aplikasi Tiket Konser Berbasis Blockchain
Smart contract : ConcertTicketing.sol (ERC-721 + status tiket + riwayat)
Framework      : Streamlit + Web3.py
Jalankan       : streamlit run app.py
"""

import base64
import html as _html
import json
import re
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from web3 import Web3

try:
    import qrcode

    HAS_QR = True
except ImportError:  # QR bersifat opsional
    HAS_QR = False

st.set_page_config(page_title="ConcertChain", page_icon="🎫", layout="wide")

# =========================================
# KONFIGURASI
# =========================================

RPC_URL = "http://127.0.0.1:8545"

PROJECT_DIR = Path(__file__).parent

DEPLOYMENT_PATH = PROJECT_DIR / "deployment.json"

ARTIFACT_PATH = (
    PROJECT_DIR
    / "artifacts"
    / "contracts"
    / "ConcertTicketing.sol"
    / "ConcertTicketing.json"
)

# Urutan harus sama dengan enum Status di smart contract
STATUS = [
    ("CREATED", "Dibuat", "#64748b"),
    ("APPROVED", "Disetujui", "#0ea5e9"),
    ("ON_SALE", "Dijual", "#8b5cf6"),
    ("SOLD", "Terjual", "#f59e0b"),
    ("VALIDATED", "Divalidasi", "#14b8a6"),
    ("CHECKED_IN", "Check-in", "#22c55e"),
    ("USED", "Terpakai", "#ef4444"),
]
GATE_FROM = 4  # status >= VALIDATED ditetapkan petugas gerbang

# =========================================
# GAYA TAMPILAN
# =========================================

st.markdown(
    """
<style>
.hero{background:linear-gradient(120deg,#6d28d9,#db2777 60%,#f59e0b);
  padding:26px 32px;border-radius:18px;color:#fff;margin-bottom:18px}
.hero h1{margin:0;font-size:2rem;color:#fff;padding:0}
.hero p{margin:4px 0 0;opacity:.92}
.badge{display:inline-block;padding:2px 11px;border-radius:999px;color:#fff;
  font-size:.75rem;font-weight:600;letter-spacing:.3px}
.stub{display:flex;border-radius:18px;overflow:hidden;color:#fff;
  background:linear-gradient(120deg,#4c1d95,#be185d);margin:6px 0 14px}
.stub-main{flex:3;padding:22px 26px}
.stub-side{flex:1;padding:22px 18px;border-left:3px dashed rgba(255,255,255,.55);
  display:flex;flex-direction:column;justify-content:center;align-items:center;
  background:rgba(0,0,0,.18);text-align:center}
.stub-label{font-size:.75rem;letter-spacing:2px;opacity:.8}
.stub-title{font-size:1.7rem;font-weight:800;margin:6px 0 4px}
.stub-id{font-size:2.2rem;font-weight:800}
.verify{padding:26px;border-radius:16px;text-align:center;color:#fff;
  font-size:1.6rem;font-weight:800;margin:10px 0}
.mono{font-family:monospace;font-size:.85rem;word-break:break-all}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================
# KONEKSI WEB3.PY
# =========================================

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 5}))

# =========================================
# CEK KONEKSI BLOCKCHAIN
# =========================================

if not w3.is_connected():
    st.error("Tidak dapat terhubung ke Hardhat Network. Pastikan Hardhat Node sedang berjalan.")
    st.stop()

# =========================================
# LOAD CONTRACT ADDRESS
# =========================================

if not DEPLOYMENT_PATH.exists():
    st.error("File deployment.json tidak ditemukan. Silakan deploy smart contract terlebih dahulu.")
    st.stop()

with open(DEPLOYMENT_PATH, "r") as file:
    deployment_data = json.load(file)

CONTRACT_ADDRESS = Web3.to_checksum_address(deployment_data["address"])

# =========================================
# LOAD CONTRACT ABI
# =========================================

if not ARTIFACT_PATH.exists():
    st.error("Artifact smart contract tidak ditemukan. Silakan compile smart contract terlebih dahulu.")
    st.stop()

with open(ARTIFACT_PATH, "r") as file:
    contract_artifact = json.load(file)

CONTRACT_ABI = contract_artifact["abi"]

# =========================================
# INISIALISASI SMART CONTRACT
# =========================================

ticket_contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

# Kontrak hasil deploy lama bisa hilang setelah node di-restart
if len(w3.eth.get_code(CONTRACT_ADDRESS)) == 0:
    st.error(
        "Tidak ada kontrak di alamat pada deployment.json. "
        "Node mungkin di-restart, silakan deploy ulang."
    )
    st.stop()

# =========================================
# FUNGSI BANTU
# =========================================

if "tx_log" not in st.session_state:
    st.session_state.tx_log = []
if "flash" not in st.session_state:
    st.session_state.flash = None


def esc(x):
    return _html.escape(str(x))


def short(addr):
    return f"{addr[:6]}…{addr[-4:]}"


def fmt_ts(ts):
    return datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M")


def badge(status):
    name, label, color = STATUS[status]
    return f'<span class="badge" style="background:{color}">{name}</span>'


def _get(obj, idx, key):
    """Struct dari web3 bisa berupa tuple atau dict; tangani keduanya."""
    return obj[key] if hasattr(obj, "keys") else obj[idx]


def parse_ticket(raw):
    t, owner, uri = raw
    price_wei = _get(t, 3, "price")
    return {
        "id": _get(t, 0, "id"),
        "event": _get(t, 1, "eventName"),
        "category": _get(t, 2, "category"),
        "price_wei": price_wei,
        "price": float(Web3.from_wei(price_wei, "ether")),
        "quota": _get(t, 4, "quota"),
        "date": _get(t, 5, "date"),
        "status": int(_get(t, 6, "status")),
        "updated": _get(t, 7, "timestamp"),
        "owner": owner,
        "uri": uri,
    }


def load_tickets():
    """Ambil semua tiket langsung dari smart contract."""
    total = ticket_contract.functions.totalTickets().call()
    return [
        parse_ticket(ticket_contract.functions.getTicket(i).call())
        for i in range(1, total + 1)
    ]


def ticket_df(tickets):
    return pd.DataFrame(
        [
            {
                "ID": t["id"],
                "Event": t["event"],
                "Kategori": t["category"],
                "Harga (ETH)": t["price"],
                "Kuota": t["quota"],
                "Tanggal": fmt_ts(t["date"]),
                "Status": STATUS[t["status"]][0],
                "Pemilik": t["owner"],
            }
            for t in tickets
        ]
    )


def revert_reason(exc):
    text = str(exc)
    for pat in (
        r"reverted with reason string '([^']*)'",
        r"execution reverted: ([^\"'\n]*)",
        r"revert(?:ed)?:? ([^\"'\n]*)",
    ):
        m = re.search(pat, text)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return text[:200]


def log_tx(action, tx_hash, status, detail=""):
    st.session_state.tx_log.insert(
        0,
        {
            "Waktu": datetime.now().strftime("%H:%M:%S"),
            "Aksi": action,
            "Status": status,
            "Tx Hash": tx_hash,
            "Detail": detail,
        },
    )


def send_tx(label, fn, sender):
    """
    Kirim transaksi: simulasi dulu (agar alasan revert terbaca jelas),
    lalu kirim, tunggu konfirmasi, dan tampilkan hasilnya.
    Mengembalikan receipt bila berhasil, None bila gagal.
    """
    try:
        fn.call({"from": sender})
    except Exception as exc:
        reason = revert_reason(exc)
        log_tx(label, "-", "❌ Ditolak", reason)
        st.error(f"❌ Transaksi ditolak kontrak: {reason}")
        return None

    try:
        with st.spinner("⏳ Menunggu konfirmasi transaksi..."):
            tx_hash = fn.transact({"from": sender})
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    except Exception as exc:
        log_tx(label, "-", "❌ Gagal", str(exc)[:150])
        st.error(f"❌ Transaksi gagal: {str(exc)[:200]}")
        return None

    h = tx_hash.hex()
    h = h if h.startswith("0x") else "0x" + h
    if receipt["status"] == 1:
        log_tx(label, h, "✅ Berhasil", f"Blok {receipt['blockNumber']}")
        st.session_state.flash = (
            "success",
            f"✅ {label} berhasil (blok {receipt['blockNumber']}, "
            f"gas {receipt['gasUsed']}). Tx: {h}",
        )
        return receipt
    log_tx(label, h, "❌ Gagal", "status 0")
    st.error("❌ Transaksi gagal dieksekusi (status 0).")
    return None


def make_qr(text):
    if not HAS_QR:
        return None
    buf = BytesIO()
    qrcode.make(text).save(buf, format="PNG")
    return buf.getvalue()


def header(title, subtitle):
    st.markdown(
        f'<div class="hero"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


# =========================================
# SIDEBAR: NAVIGASI + WALLET AKTIF
# =========================================

P_DASH = "🏠 Dashboard"
P_LIST = "🎪 Daftar Tiket"
P_CREATE = "➕ Terbitkan Tiket"
P_DETAIL = "🔎 Detail Tiket"
P_MINE = "🎟️ Tiket Saya & Transfer"
P_STATUS = "🔄 Kelola Status"
P_VERIFY = "✅ Verifikasi Tiket"
P_WALLET = "👛 Wallet & Transaksi"
PAGES = [P_DASH, P_LIST, P_CREATE, P_DETAIL, P_MINE, P_STATUS, P_VERIFY, P_WALLET]

promoter_addr = ticket_contract.functions.promoter().call()
accounts = w3.eth.accounts
if not accounts:
    st.error("Node tidak menyediakan akun. Gunakan `npx hardhat node`.")
    st.stop()


def role_of(addr):
    if addr.lower() == promoter_addr.lower():
        return "Promotor"
    if ticket_contract.functions.isGate(addr).call():
        return "Petugas Gerbang"
    return "Pengunjung"


with st.sidebar:
    st.markdown("## 🎫 ConcertChain")
    st.caption("Tiket konser NFT di atas blockchain")
    st.radio("Navigasi", PAGES, key="nav")
    st.divider()
    idx = st.selectbox(
        "Wallet aktif",
        list(range(len(accounts))),
        format_func=lambda i: f"#{i} · {short(accounts[i])} · {role_of(accounts[i])}",
    )
    active = accounts[idx]
    active_role = role_of(active)
    st.caption(f"Peran: **{active_role}**")
    st.caption(f"Saldo: {float(Web3.from_wei(w3.eth.get_balance(active), 'ether')):.4f} ETH")
    st.divider()
    st.success(f"🟢 Terhubung · blok {w3.eth.block_number}")


def goto_detail(ticket_id):
    st.session_state["detail_id"] = ticket_id
    st.session_state["nav"] = P_DETAIL


# =========================================
# HALAMAN 1: DASHBOARD
# =========================================


def page_dashboard():
    header("ConcertChain", "Penerbitan, kepemilikan, dan validasi tiket konser yang transparan.")
    tickets = load_tickets()

    c = st.columns(4)
    c[0].metric("Total Tiket", len(tickets))
    c[1].metric("Jumlah Event", len({t["event"] for t in tickets}))
    c[2].metric("Tiket Terjual", sum(1 for t in tickets if t["status"] >= 3))
    c[3].metric("Check-in / Terpakai", sum(1 for t in tickets if t["status"] >= 5))

    st.subheader("Status Koneksi Blockchain")
    a, b = st.columns(2)
    with a:
        st.markdown(
            f"- **Status:** 🟢 Terhubung\n"
            f"- **Chain ID:** {w3.eth.chain_id}\n"
            f"- **Blok terakhir:** {w3.eth.block_number}\n"
            f"- **RPC:** `{RPC_URL}`"
        )
    with b:
        st.markdown(
            f"- **Kontrak:** {ticket_contract.functions.name().call()} "
            f"({ticket_contract.functions.symbol().call()})\n"
            f"- **Alamat:** <span class='mono'>{CONTRACT_ADDRESS}</span>\n"
            f"- **Promotor:** <span class='mono'>{promoter_addr}</span>",
            unsafe_allow_html=True,
        )

    st.subheader("Alur Status Tiket")
    cols = st.columns(len(STATUS))
    counts = []
    for i, (name, label, _) in enumerate(STATUS):
        n = sum(1 for t in tickets if t["status"] == i)
        counts.append(n)
        cols[i].metric(label, n)
    st.caption("CREATED → APPROVED → ON_SALE → SOLD (promotor) → VALIDATED → CHECKED_IN → USED (petugas gerbang)")

    if tickets:
        st.bar_chart(pd.DataFrame({"Jumlah tiket": counts}, index=[s[1] for s in STATUS]))
        st.subheader("Tiket Terbaru")
        st.dataframe(ticket_df(tickets[-5:][::-1]), hide_index=True)
    else:
        st.info("Belum ada tiket. Promotor dapat menerbitkan tiket di menu **Terbitkan Tiket**.")


# =========================================
# HALAMAN 2: DAFTAR TIKET (DATA MANAGEMENT)
# =========================================


def page_list():
    header("Daftar Tiket", "Seluruh data dibaca langsung dari smart contract.")
    tickets = load_tickets()
    if not tickets:
        st.info("Belum ada tiket yang diterbitkan.")
        return

    f1, f2, f3 = st.columns([2, 1, 2])
    q = f1.text_input("Cari event", placeholder="Nama event...")
    cats = sorted({t["category"] for t in tickets})
    cat = f2.selectbox("Kategori", ["Semua"] + cats)
    stat = f3.multiselect("Status", [s[0] for s in STATUS])

    shown = [
        t
        for t in tickets
        if (not q or q.lower() in t["event"].lower())
        and (cat == "Semua" or t["category"] == cat)
        and (not stat or STATUS[t["status"]][0] in stat)
    ]
    st.caption(f"Menampilkan {len(shown)} dari {len(tickets)} tiket")

    tab_card, tab_table = st.tabs(["🎴 Kartu", "📋 Tabel"])
    with tab_card:
        cols = st.columns(3)
        for i, t in enumerate(shown):
            with cols[i % 3].container(border=True):
                st.markdown(
                    f"**#{t['id']} · {esc(t['event'])}**<br>"
                    f"{esc(t['category'])} · {fmt_ts(t['date'])}<br>"
                    f"💰 {t['price']:g} ETH · 👥 kuota {t['quota']}<br>"
                    f"{badge(t['status'])}",
                    unsafe_allow_html=True,
                )
                st.caption(f"Pemilik: {short(t['owner'])}")
                st.button("Lihat Detail", key=f"d{t['id']}", on_click=goto_detail, args=(t["id"],))
    with tab_table:
        st.dataframe(ticket_df(shown), hide_index=True)


# =========================================
# HALAMAN 3: TERBITKAN TIKET (FORM INPUT)
# =========================================


def page_create():
    header("Terbitkan Tiket", "Hanya promotor yang dapat membuat tiket baru.")
    is_promoter = active.lower() == promoter_addr.lower()
    if not is_promoter:
        st.warning("Wallet aktif bukan promotor. Pilih akun promotor di sidebar untuk menerbitkan tiket.")

    with st.form("create_form"):
        c1, c2 = st.columns(2)
        event_name = c1.text_input("Nama event", placeholder="Contoh: Konser Tulus Jakarta")
        cat_choice = c2.selectbox("Kategori tiket", ["Regular", "VIP", "VVIP", "Festival", "Early Bird", "Lainnya"])
        cat_other = c2.text_input("Kategori lain (jika memilih Lainnya)")

        c3, c4 = st.columns(2)
        price = c3.number_input("Harga (ETH)", min_value=0.0, value=0.05, step=0.01, format="%.4f")
        quota = c4.number_input("Kuota", min_value=0, value=100, step=1)

        c5, c6 = st.columns(2)
        d = c5.date_input("Tanggal konser", min_value=datetime.now().date())
        tm = c6.time_input("Jam mulai", value=datetime.strptime("19:00", "%H:%M").time())

        st.markdown("**Metadata NFT**")
        auto = st.checkbox("Buat metadata otomatis", value=True)
        venue = st.text_input("Lokasi / venue", placeholder="Contoh: Istora Senayan")
        desc = st.text_area("Deskripsi", placeholder="Deskripsi singkat event", height=80)
        manual_uri = st.text_input("URI metadata manual (ipfs:// atau https://)", disabled=auto)

        submit = st.form_submit_button("🎫 Terbitkan Tiket", disabled=not is_promoter)

    if not submit:
        return

    category = cat_other.strip() if cat_choice == "Lainnya" else cat_choice
    errors = []
    if len(event_name.strip()) < 3:
        errors.append("Nama event minimal 3 karakter.")
    if len(event_name.strip()) > 100:
        errors.append("Nama event maksimal 100 karakter.")
    if not category:
        errors.append("Kategori tidak boleh kosong.")
    if price <= 0:
        errors.append("Harga harus lebih dari 0.")
    if quota <= 0:
        errors.append("Kuota harus lebih dari 0.")

    ts = int(datetime.combine(d, tm).timestamp())
    if ts <= w3.eth.get_block("latest")["timestamp"]:
        errors.append("Tanggal dan jam konser harus di masa depan.")

    if auto:
        if not venue.strip():
            errors.append("Lokasi wajib diisi untuk metadata otomatis.")
        meta = {
            "name": f"{event_name.strip()} - {category}",
            "description": desc.strip(),
            "attributes": [
                {"trait_type": "Venue", "value": venue.strip()},
                {"trait_type": "Category", "value": category},
            ],
        }
        uri = "data:application/json;base64," + base64.b64encode(
            json.dumps(meta).encode()
        ).decode()
    else:
        uri = manual_uri.strip()
        if not re.match(r"^(ipfs|https?)://\S+$", uri):
            errors.append("URI metadata harus diawali ipfs://, http://, atau https://.")

    if errors:
        for e in errors:
            st.error(e)
        return

    try:
        price_wei = Web3.to_wei(Decimal(str(price)), "ether")
    except InvalidOperation:
        st.error("Harga tidak valid.")
        return

    fn = ticket_contract.functions.createTicket(
        event_name.strip(), category, price_wei, int(quota), ts, uri
    )
    if send_tx("Terbitkan tiket", fn, active):
        st.rerun()


# =========================================
# HALAMAN 4: DETAIL TIKET
# =========================================


def page_detail():
    header("Detail Tiket", "Informasi lengkap, QR Code, dan riwayat tiket dari blockchain.")
    total = ticket_contract.functions.totalTickets().call()
    if total == 0:
        st.info("Belum ada tiket.")
        return

    ids = list(range(1, total + 1))
    if st.session_state.get("detail_id") not in ids:
        st.session_state["detail_id"] = ids[0]
    tid = st.selectbox("Pilih ID tiket", ids, key="detail_id")

    t = parse_ticket(ticket_contract.functions.getTicket(tid).call())
    st.markdown(
        f"""
<div class="stub">
  <div class="stub-main">
    <div class="stub-label">CONCERT TICKET</div>
    <div class="stub-title">{esc(t['event'])}</div>
    <div>{esc(t['category'])} · {fmt_ts(t['date'])}</div>
    <div style="margin-top:10px">{badge(t['status'])}</div>
  </div>
  <div class="stub-side">
    <div class="stub-label">TIKET</div>
    <div class="stub-id">#{t['id']}</div>
    <div>{t['price']:g} ETH</div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )
    st.progress(t["status"] / (len(STATUS) - 1), text=f"Tahap {t['status'] + 1} dari {len(STATUS)}: {STATUS[t['status']][1]}")

    a, b = st.columns([2, 1])
    with a:
        st.markdown(
            f"- **Pemilik saat ini:** <span class='mono'>{t['owner']}</span>\n"
            f"- **Promotor (penerbit):** <span class='mono'>{promoter_addr}</span>\n"
            f"- **Kuota:** {t['quota']}\n"
            f"- **Terakhir diperbarui:** {fmt_ts(t['updated'])}",
            unsafe_allow_html=True,
        )
        if t["uri"].startswith("data:application/json;base64,"):
            with st.expander("Metadata NFT"):
                try:
                    st.json(json.loads(base64.b64decode(t["uri"].split(",", 1)[1])))
                except Exception:
                    st.code(t["uri"])
        else:
            st.markdown(f"**Metadata URI:** `{t['uri']}`")
    with b:
        png = make_qr(f"CTIX|{CONTRACT_ADDRESS}|{t['id']}")
        if png:
            st.image(png, caption="QR Code tiket", width=190)
        else:
            st.info("Pasang `qrcode[pil]` untuk menampilkan QR Code.")

    st.subheader("Riwayat Tiket (terbaru → terlama)")
    hist = ticket_contract.functions.getHistory(tid).call()
    rows = [
        {
            "Waktu": fmt_ts(_get(h, 4, "timestamp")),
            "Aksi": _get(h, 0, "action"),
            "Pelaku": _get(h, 1, "actor"),
            "Pemilik": _get(h, 2, "owner"),
            "Status": STATUS[int(_get(h, 3, "status"))][0],
        }
        for h in hist
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True)


# =========================================
# HALAMAN 5: TIKET SAYA & TRANSFER
# =========================================


def page_mine():
    header("Tiket Saya & Transfer", "Tiket milik wallet aktif dan pemindahan kepemilikan.")
    mine = [t for t in load_tickets() if t["owner"].lower() == active.lower()]
    st.markdown(f"Wallet aktif: <span class='mono'>{active}</span>", unsafe_allow_html=True)
    if not mine:
        st.info("Wallet ini belum memiliki tiket.")
        return

    st.dataframe(ticket_df(mine).drop(columns=["Pemilik"]), hide_index=True)

    st.subheader("Transfer / Pembelian Tiket")
    st.caption(
        "Kontrak tidak memiliki fungsi pembayaran. Pembelian disimulasikan sebagai "
        "transfer kepemilikan dari pemilik tiket ke pembeli."
    )
    transferable = [t for t in mine if t["status"] < 5]
    if not transferable:
        st.warning("Semua tiket Anda sudah check-in/terpakai sehingga tidak dapat ditransfer.")
        return

    tid = st.selectbox(
        "Tiket yang dipindahkan",
        [t["id"] for t in transferable],
        format_func=lambda i: f"#{i} · {next(t['event'] for t in transferable if t['id'] == i)}",
    )
    pick = st.selectbox(
        "Pilih penerima dari akun Hardhat",
        ["(ketik manual)"] + [f"#{i} · {a}" for i, a in enumerate(accounts) if a.lower() != active.lower()],
    )
    manual = st.text_input("Alamat penerima", value="" if pick == "(ketik manual)" else pick.split(" · ")[1])
    confirm = st.checkbox("Saya yakin ingin memindahkan tiket ini")

    if st.button("🚀 Kirim Transfer", disabled=not confirm):
        to = manual.strip()
        if not Web3.is_address(to):
            st.error("Alamat penerima tidak valid.")
        elif to.lower() == active.lower():
            st.error("Penerima tidak boleh sama dengan pengirim.")
        elif int(to, 16) == 0:
            st.error("Alamat tujuan tidak boleh alamat nol.")
        else:
            fn = ticket_contract.functions.transferTicket(tid, Web3.to_checksum_address(to))
            if send_tx(f"Transfer tiket #{tid}", fn, active):
                st.rerun()


# =========================================
# HALAMAN 6: KELOLA STATUS
# =========================================


def page_status():
    header("Kelola Status Tiket", "Status maju satu tahap, oleh pihak yang berwenang.")
    tickets = load_tickets()
    if not tickets:
        st.info("Belum ada tiket.")
        return

    st.markdown(
        "| Tahap | Pihak berwenang |\n|---|---|\n"
        "| APPROVED, ON_SALE, SOLD | Promotor |\n"
        "| VALIDATED, CHECKED_IN, USED | Petugas gerbang |"
    )
    tid = st.selectbox(
        "Pilih tiket",
        [t["id"] for t in tickets],
        format_func=lambda i: f"#{i} · {tickets[i - 1]['event']} ({STATUS[tickets[i - 1]['status']][0]})",
    )
    t = tickets[tid - 1]
    st.markdown(f"Status saat ini: {badge(t['status'])}", unsafe_allow_html=True)

    if t["status"] >= len(STATUS) - 1:
        st.info("Tiket sudah USED. Status akhir, tidak dapat diubah lagi.")
        return

    nxt = t["status"] + 1
    needed = "Petugas Gerbang" if nxt >= GATE_FROM else "Promotor"
    st.markdown(f"Tahap berikutnya: {badge(nxt)} · wajib ditetapkan oleh **{needed}**", unsafe_allow_html=True)
    if active_role != needed:
        st.warning(f"Wallet aktif berperan **{active_role}**. Ganti ke akun {needed} di sidebar.")

    if st.button(f"➡️ Ubah ke {STATUS[nxt][0]}", disabled=active_role != needed):
        if send_tx(f"Status tiket #{tid} → {STATUS[nxt][0]}", ticket_contract.functions.updateStatus(tid, nxt), active):
            st.rerun()


# =========================================
# HALAMAN 7: VERIFIKASI TIKET
# =========================================


def page_verify():
    header("Verifikasi Tiket", "Untuk petugas gerbang: cek keabsahan tiket dari ID atau QR Code.")
    c1, c2 = st.columns(2)
    tid = c1.number_input("ID tiket", min_value=1, value=1, step=1)
    wallet = c2.text_input("Wallet pemegang tiket (opsional)")

    if not st.button("🔍 Verifikasi"):
        return

    total = ticket_contract.functions.totalTickets().call()
    if tid > total:
        verdict, color, note = "INVALID", "#ef4444", "Tiket tidak terdaftar di smart contract."
        t = None
    else:
        t = parse_ticket(ticket_contract.functions.getTicket(int(tid)).call())
        if t["status"] == 6:
            verdict, color, note = "SUDAH DIPAKAI", "#f59e0b", "Tiket sudah berstatus USED."
        elif t["status"] >= 3:
            verdict, color, note = "VALID", "#22c55e", "Tiket sah dan belum dipakai."
        else:
            verdict, color, note = "BELUM VALID", "#64748b", "Tiket belum terjual (belum berstatus SOLD)."

    st.markdown(f'<div class="verify" style="background:{color}">{verdict}</div>', unsafe_allow_html=True)
    st.write(note)
    if t:
        st.markdown(
            f"**{esc(t['event'])}** · {esc(t['category'])} · {fmt_ts(t['date'])}<br>"
            f"Status: {badge(t['status'])}<br>"
            f"Pemilik: <span class='mono'>{t['owner']}</span>",
            unsafe_allow_html=True,
        )
        if wallet.strip():
            if not Web3.is_address(wallet.strip()):
                st.error("Alamat wallet tidak valid.")
            elif wallet.strip().lower() == t["owner"].lower():
                st.success("✅ Wallet cocok dengan pemilik tiket.")
            else:
                st.error("❌ Wallet BUKAN pemilik tiket ini.")


# =========================================
# HALAMAN 8: WALLET & TRANSAKSI
# =========================================


def page_wallet():
    header("Wallet & Transaksi", "Alamat wallet, peran, saldo, dan status transaksi.")
    st.markdown(f"**Wallet aktif:** <span class='mono'>{active}</span>", unsafe_allow_html=True)
    c = st.columns(3)
    c[0].metric("Peran", active_role)
    c[1].metric("Saldo (ETH)", f"{float(Web3.from_wei(w3.eth.get_balance(active), 'ether')):.4f}")
    c[2].metric("Jumlah transaksi (nonce)", w3.eth.get_transaction_count(active))

    st.subheader("Daftar Akun")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "#": i,
                    "Alamat": a,
                    "Peran": role_of(a),
                    "Saldo (ETH)": round(float(Web3.from_wei(w3.eth.get_balance(a), "ether")), 4),
                }
                for i, a in enumerate(accounts)
            ]
        ),
        hide_index=True,
    )

    st.subheader("Status Transaksi (sesi ini)")
    if st.session_state.tx_log:
        st.dataframe(pd.DataFrame(st.session_state.tx_log), hide_index=True)
    else:
        st.info("Belum ada transaksi pada sesi ini.")

    st.subheader("Administrasi Petugas Gerbang")
    st.caption("Hanya promotor yang dapat menunjuk atau mencabut petugas gerbang.")
    target = st.selectbox("Akun", accounts, format_func=lambda a: f"{short(a)} · {role_of(a)}", key="gate_target")
    allow = st.radio("Tindakan", ["Tunjuk sebagai petugas gerbang", "Cabut akses"], horizontal=True)
    if st.button("Simpan perubahan"):
        fn = ticket_contract.functions.setGate(target, allow.startswith("Tunjuk"))
        if send_tx("Atur petugas gerbang", fn, active):
            st.rerun()


# =========================================
# ROUTER
# =========================================

if st.session_state.flash:
    kind, msg = st.session_state.flash
    st.session_state.flash = None
    st.success(msg)

{
    P_DASH: page_dashboard,
    P_LIST: page_list,
    P_CREATE: page_create,
    P_DETAIL: page_detail,
    P_MINE: page_mine,
    P_STATUS: page_status,
    P_VERIFY: page_verify,
    P_WALLET: page_wallet,
}[st.session_state["nav"]]()