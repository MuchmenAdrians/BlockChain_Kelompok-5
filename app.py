import json
import time
from datetime import datetime

import streamlit as st
import streamlit.components.v2 as components
from web3 import Web3

# =========================================================
# KONFIGURASI
# =========================================================

RPC_URL = "http://127.0.0.1:8545"
PRICE_LABEL = "Rp"      # ubah sesuai satuan harga yang dipakai kelompok
MAX_SCAN = 100          # batas jumlah tiket yang dipindai untuk daftar

STATUS_NAMES = [
    "CREATED", "APPROVED", "ON_SALE", "SOLD",
    "VALIDATED", "CHECKED_IN", "USED",
]
STATUS_LABELS = {
    "CREATED": "Dibuat",
    "APPROVED": "Disetujui",
    "ON_SALE": "Dijual",
    "SOLD": "Terjual",
    "VALIDATED": "Divalidasi",
    "CHECKED_IN": "Check-in",
    "USED": "Dipakai",
}
STATUS_COLORS = {
    "CREATED": "gray",
    "APPROVED": "blue",
    "ON_SALE": "orange",
    "SOLD": "green",
    "VALIDATED": "violet",
    "CHECKED_IN": "primary",
    "USED": "red",
}
ACTION_LABELS = {
    "TICKET_CREATED": "🆕 Tiket dibuat",
    "STATUS_UPDATED": "🔄 Status diperbarui",
    "OWNERSHIP_TRANSFERRED": "🔁 Kepemilikan dipindahkan",
}

TICKET_TUPLE = {
    "type": "tuple",
    "name": "ticket",
    "components": [
        {"name": "id", "type": "uint256"},
        {"name": "eventName", "type": "string"},
        {"name": "category", "type": "string"},
        {"name": "price", "type": "uint256"},
        {"name": "quota", "type": "uint256"},
        {"name": "date", "type": "uint256"},
        {"name": "status", "type": "uint8"},
        {"name": "timestamp", "type": "uint256"},
    ],
}

# ABI minimal (hanya fungsi baca) dari ConcertTicketing.sol
CONTRACT_ABI = json.loads(json.dumps([
    {"type": "function", "name": "name", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "string"}]},
    {"type": "function", "name": "symbol", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "string"}]},
    {"type": "function", "name": "promoter", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "address"}]},
    {"type": "function", "name": "isGate", "stateMutability": "view",
     "inputs": [{"name": "", "type": "address"}],
     "outputs": [{"name": "", "type": "bool"}]},
    {"type": "function", "name": "totalTickets", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "uint256"}]},
    {"type": "function", "name": "getOwner", "stateMutability": "view",
     "inputs": [{"name": "_ticketId", "type": "uint256"}],
     "outputs": [{"name": "", "type": "address"}]},
    {"type": "function", "name": "getTicket", "stateMutability": "view",
     "inputs": [{"name": "_ticketId", "type": "uint256"}],
     "outputs": [
         TICKET_TUPLE,
         {"name": "ticketOwner", "type": "address"},
         {"name": "metadataURI", "type": "string"},
     ]},
    {"type": "function", "name": "getHistory", "stateMutability": "view",
     "inputs": [{"name": "_ticketId", "type": "uint256"}],
     "outputs": [{
         "type": "tuple[]",
         "name": "",
         "components": [
             {"name": "action", "type": "string"},
             {"name": "actor", "type": "address"},
             {"name": "owner", "type": "address"},
             {"name": "status", "type": "uint8"},
             {"name": "timestamp", "type": "uint256"},
         ],
     }]},
]))

st.set_page_config(
    page_title="Concert Ticketing NFT",
    page_icon="🎫",
    layout="centered",
)

st.title("🎫 Concert Ticketing NFT")
st.caption(
    "Kelompok 5 · ERC-721 · Hardhat + MetaMask + Streamlit + Web3.py"
)
st.write(
    "Tiket konser sebagai NFT. Setiap tiket tercatat di blockchain, "
    "riwayatnya bisa dilacak, dan tidak bisa dipalsukan."
)

# =========================================================
# KOMPONEN JAVASCRIPT UNTUK METAMASK
# =========================================================

WALLET_HTML = """
<div>
  <button id="connect-wallet" type="button">
    🦊 Connect Wallet
  </button>
  <p id="wallet-status">Wallet belum terhubung.</p>
</div>
"""

WALLET_CSS = """
button {
    padding: 0.7rem 1.1rem;
    border: none;
    border-radius: 10px;
    background: var(--st-primary-color);
    color: white;
    font-weight: 600;
    cursor: pointer;
}

p {
    color: var(--st-text-color);
    overflow-wrap: anywhere;
}
"""

WALLET_JS = """
export default function(component) {
    const { parentElement, setStateValue } = component;

    const button = parentElement.querySelector("#connect-wallet");
    const status = parentElement.querySelector("#wallet-status");

    let mounted = true;

    async function readWallet() {
        if (!window.ethereum) {
            return;
        }

        const accounts = await window.ethereum.request({
            method: "eth_accounts"
        });

        const chainId = await window.ethereum.request({
            method: "eth_chainId"
        });

        if (!mounted) return;

        if (accounts && accounts.length > 0) {
            setStateValue("wallet", {
                address: accounts[0],
                chainId: chainId,
                connected: true
            });
            status.textContent = "Wallet terhubung: " + accounts[0];
        } else {
            setStateValue("wallet", {
                address: "",
                chainId: chainId,
                connected: false
            });
            status.textContent = "Wallet belum terhubung.";
        }
    }

    async function connectWallet() {
        if (!window.ethereum) {
            status.textContent =
                "MetaMask tidak ditemukan. Pasang ekstensi MetaMask.";
            return;
        }

        try {
            status.textContent =
                "Menunggu persetujuan akses akun...";

            await window.ethereum.request({
                method: "eth_requestAccounts"
            });

            await readWallet();
        } catch (error) {
            status.textContent =
                "Koneksi gagal: " +
                (error.message || "Kesalahan tidak diketahui");
        }
    }

    function onAccountsChanged(accounts) {
        if (!mounted) return;

        window.ethereum.request({ method: "eth_chainId" })
            .then((chainId) => {
                if (!mounted) return;

                if (accounts && accounts.length > 0) {
                    setStateValue("wallet", {
                        address: accounts[0],
                        chainId: chainId,
                        connected: true
                    });
                    status.textContent =
                        "Wallet terhubung: " + accounts[0];
                } else {
                    setStateValue("wallet", {
                        address: "",
                        chainId: chainId,
                        connected: false
                    });
                    status.textContent = "Akun tidak terhubung.";
                }
            })
            .catch(() => {});
    }

    function onChainChanged(chainId) {
        if (!mounted) return;

        window.ethereum.request({ method: "eth_accounts" })
            .then((accounts) => {
                if (!mounted) return;

                setStateValue("wallet", {
                    address: accounts && accounts.length > 0
                        ? accounts[0]
                        : "",
                    chainId: chainId,
                    connected: Boolean(accounts && accounts.length > 0)
                });
            })
            .catch(() => {});
    }

    button.addEventListener("click", connectWallet);

    if (window.ethereum) {
        window.ethereum.on("accountsChanged", onAccountsChanged);
        window.ethereum.on("chainChanged", onChainChanged);

        // Baca koneksi yang sudah pernah diberikan izin.
        readWallet().catch(() => {});
    }

    return () => {
        mounted = false;
        button.removeEventListener("click", connectWallet);

        if (window.ethereum && window.ethereum.removeListener) {
            window.ethereum.removeListener(
                "accountsChanged", onAccountsChanged
            );
            window.ethereum.removeListener(
                "chainChanged", onChainChanged
            );
        }
    };
}
"""

wallet_component = components.component(
    name="concert_metamask_wallet",
    html=WALLET_HTML,
    css=WALLET_CSS,
    js=WALLET_JS,
)


# =========================================================
# FUNGSI BANTU
# =========================================================

def short(addr: str) -> str:
    addr = str(addr)
    return addr[:6] + "…" + addr[-4:] if len(addr) > 12 else addr


def fmt_time(ts: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d %b %Y %H:%M")
    except (ValueError, OverflowError, OSError):
        return str(ts)


def fmt_price(value: int) -> str:
    return f"{PRICE_LABEL} {int(value):,}".replace(",", ".")


def countdown(ts: int) -> str:
    delta = int(ts) - time.time()
    if delta < 0:
        return "sudah lewat"
    days = int(delta // 86400)
    return "hari ini" if days == 0 else f"H-{days}"


def status_name(idx: int) -> str:
    idx = int(idx)
    return STATUS_NAMES[idx] if 0 <= idx < len(STATUS_NAMES) else str(idx)


def status_badge(idx: int):
    name = status_name(idx)
    st.badge(
        STATUS_LABELS.get(name, name),
        color=STATUS_COLORS.get(name, "gray"),
    )


def parse_ticket(raw):
    """raw = hasil getTicket: (tuple tiket, owner, uri)."""
    t = raw[0]
    return {
        "id": int(t[0]),
        "event": t[1],
        "category": t[2],
        "price": int(t[3]),
        "quota": int(t[4]),
        "date": int(t[5]),
        "status": int(t[6]),
        "timestamp": int(t[7]),
        "owner": raw[1],
        "uri": raw[2],
    }


def ticket_card(tk):
    with st.container(border=True):
        left, right = st.columns([3, 1])
        with left:
            st.subheader(tk["event"])
            st.caption(
                f"📅 {fmt_time(tk['date'])} · {countdown(tk['date'])}"
            )
            st.caption(
                f"🎭 Kategori {tk['category']} · kuota {tk['quota']}"
            )
            st.caption(f"👤 Pemilik {short(tk['owner'])}")
        with right:
            st.metric("Tiket", f"#{tk['id']}")
            status_badge(tk["status"])
            st.caption(fmt_price(tk["price"]))


def stepper(current: int):
    steps = []
    for i, name in enumerate(STATUS_NAMES):
        icon = "✅" if i < current else ("🔵" if i == current else "⚪")
        steps.append(f"{icon} {STATUS_LABELS[name]}")
    st.progress(
        current / (len(STATUS_NAMES) - 1),
        text=f"Tahap {current + 1} dari {len(STATUS_NAMES)}",
    )
    st.markdown("  →  ".join(steps))


def timeline(history):
    for h in history:
        action = ACTION_LABELS.get(h[0], h[0])
        with st.container(border=True):
            top, badge_col = st.columns([3, 1])
            top.markdown(f"**{action}**")
            with badge_col:
                status_badge(h[3])
            st.caption(
                f"Oleh {short(h[1])} · pemilik {short(h[2])} · "
                f"🕒 {fmt_time(h[4])}"
            )


# =========================================================
# SIDEBAR: PENGATURAN KONTRAK
# =========================================================

with st.sidebar:
    st.header("⚙️ Pengaturan")
    contract_address = st.text_input(
        "Alamat kontrak",
        placeholder="0x...",
        help="Salin dari output: npx hardhat run scripts/deploy.js "
             "--network localhost",
    )
    st.caption(
        "Kalau node Hardhat dijalankan ulang, kontrak harus di-deploy "
        "ulang dan alamat di sini diperbarui."
    )

# =========================================================
# 1. STATUS BLOCKCHAIN
# =========================================================

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 5}))
rpc_connected = w3.is_connected()

st.divider()
st.subheader("⛓️ 1. Blockchain Lokal")

if rpc_connected:
    c1, c2, c3 = st.columns(3)
    c1.metric("Status", "Terhubung ✅")
    c2.metric("Chain ID", w3.eth.chain_id)
    c3.metric("Block", w3.eth.block_number)
else:
    st.error(
        "Hardhat RPC tidak dapat diakses. "
        "Jalankan 'npx hardhat node' pada terminal lain."
    )

# =========================================================
# 2. KONEKSI METAMASK
# =========================================================

st.divider()
st.subheader("🦊 2. Hubungkan MetaMask")

wallet_result = wallet_component(
    key="concert_metamask",
    default={
        "wallet": {
            "address": "",
            "chainId": "",
            "connected": False,
        }
    },
    on_wallet_change=lambda: None,
)

wallet = wallet_result.wallet

# =========================================================
# 3. INFORMASI WALLET DAN SALDO
# =========================================================

st.divider()
st.subheader("👛 3. Wallet Anda")

address = None

if wallet and wallet.get("connected") and wallet.get("address"):
    address = Web3.to_checksum_address(wallet["address"])

    try:
        wallet_chain_id = int(wallet["chainId"], 16)

        w1, w2 = st.columns(2)
        w1.metric("Alamat", short(address))
        w2.metric("Chain ID MetaMask", wallet_chain_id)
        st.code(address)

        if not rpc_connected:
            st.warning(
                "Wallet terhubung, tetapi RPC tidak tersedia. "
                "Saldo belum dapat dibaca."
            )
        elif wallet_chain_id != w3.eth.chain_id:
            st.warning(
                "Jaringan MetaMask berbeda dengan jaringan RPC Python. "
                "Pilih jaringan Hardhat Local (Chain ID 31337) pada MetaMask."
            )
        else:
            st.success("Jaringan wallet sesuai dengan RPC.")

            if st.button("💰 Periksa Saldo ETH", type="primary"):
                try:
                    balance_eth = w3.from_wei(
                        w3.eth.get_balance(address), "ether"
                    )
                    st.metric("Saldo ETH", f"{float(balance_eth):,.4f} ETH")
                    st.caption("Saldo dibaca oleh Web3.py dari Hardhat RPC.")
                except Exception as error:
                    st.error("Gagal membaca saldo wallet.")
                    st.caption(str(error))

    except (ValueError, TypeError) as error:
        st.error("Data Chain ID dari MetaMask tidak valid.")
        st.caption(str(error))
else:
    st.info(
        "Klik Connect Wallet, kemudian setujui akses akun di MetaMask."
    )

# =========================================================
# 4. KONTRAK CONCERTTICKETING
# =========================================================

st.divider()
st.subheader("🎟️ 4. Kontrak Tiket")

contract = None

if not rpc_connected:
    st.info("Hubungkan Hardhat RPC terlebih dahulu.")
elif not contract_address:
    st.info(
        "Isi **Alamat kontrak** di sidebar (panah kecil di kiri atas) "
        "setelah deploy berhasil."
    )
elif not Web3.is_address(contract_address):
    st.error("Format alamat kontrak tidak valid.")
else:
    checksum = Web3.to_checksum_address(contract_address)
    if len(w3.eth.get_code(checksum)) == 0:
        st.error(
            "Tidak ada kontrak di alamat ini. Jika node Hardhat dijalankan "
            "ulang, kontrak harus di-deploy ulang."
        )
    else:
        contract = w3.eth.contract(address=checksum, abi=CONTRACT_ABI)

if contract is not None:
    try:
        promoter_addr = contract.functions.promoter().call()
        total = contract.functions.totalTickets().call()
        token_name = contract.functions.name().call()
        token_symbol = contract.functions.symbol().call()
    except Exception as error:
        st.error("Gagal membaca kontrak. Pastikan alamat kontrak benar.")
        st.caption(str(error))
        contract = None

if contract is not None:
    k1, k2, k3 = st.columns(3)
    k1.metric("Token", f"{token_name} ({token_symbol})")
    k2.metric("Total tiket", total)
    k3.metric("Promotor", short(promoter_addr))

    # ---- Peran wallet ----
    if address:
        if address == promoter_addr:
            role, role_desc = "🎤 Promotor", (
                "Membuat tiket dan mengubah status sampai SOLD."
            )
        elif contract.functions.isGate(address).call():
            role, role_desc = "🚪 Petugas Gerbang", (
                "Menetapkan status VALIDATED, CHECKED_IN, dan USED."
            )
        else:
            role, role_desc = "🙋 Pemilik / Pengunjung", (
                "Memindahkan tiket selama belum CHECKED_IN."
            )
        st.write("Peran wallet Anda:")
        st.badge(role, color="violet")
        st.caption(role_desc)

    tab_mine, tab_all, tab_detail = st.tabs(
        ["🎫 Tiket Saya", "🌐 Semua Tiket", "🔍 Detail & Riwayat"]
    )

    scan_to = min(int(total), MAX_SCAN)

    # ---- Tiket milik wallet ----
    with tab_mine:
        if not address:
            st.info("Hubungkan wallet untuk melihat tiket Anda.")
        elif total == 0:
            st.info("Belum ada tiket yang dibuat.")
        else:
            owned = []
            for tid in range(1, scan_to + 1):
                try:
                    if contract.functions.getOwner(tid).call() == address:
                        owned.append(tid)
                except Exception:
                    pass

            if owned:
                st.caption(f"Anda memiliki {len(owned)} tiket.")
                for tid in owned:
                    ticket_card(
                        parse_ticket(contract.functions.getTicket(tid).call())
                    )
            else:
                st.info("Wallet ini belum memiliki tiket.")

    # ---- Semua tiket ----
    with tab_all:
        if total == 0:
            st.info("Belum ada tiket yang dibuat.")
        else:
            if total > scan_to:
                st.caption(f"Menampilkan {scan_to} tiket pertama.")
            for tid in range(1, scan_to + 1):
                try:
                    ticket_card(
                        parse_ticket(contract.functions.getTicket(tid).call())
                    )
                except Exception:
                    pass

    # ---- Detail dan riwayat ----
    with tab_detail:
        if total == 0:
            st.info("Belum ada tiket untuk ditampilkan.")
        else:
            ticket_id = st.number_input(
                "ID tiket", min_value=1, max_value=int(total),
                value=1, step=1,
            )

            try:
                tk = parse_ticket(
                    contract.functions.getTicket(int(ticket_id)).call()
                )

                ticket_card(tk)

                st.markdown("**Perjalanan tiket**")
                stepper(tk["status"])

                st.write("Pemilik saat ini:")
                st.code(tk["owner"])
                st.write("URI metadata:")
                st.code(tk["uri"])
                st.caption(
                    f"Terakhir diperbarui: {fmt_time(tk['timestamp'])}"
                )

                st.markdown("**Riwayat (terbaru ke terlama)**")
                timeline(
                    contract.functions.getHistory(int(ticket_id)).call()
                )

            except Exception as error:
                st.error("Gagal membaca data tiket.")
                st.caption(str(error))

# =========================================================
# CATATAN
# =========================================================

st.divider()
st.caption(
    "Prototipe ini hanya membaca data blockchain (saldo, tiket, riwayat). "
    "Tidak ada transaksi transfer atau perubahan smart contract."
)