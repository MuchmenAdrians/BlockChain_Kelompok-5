// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";

/// @title ConcertTicketing
/// @notice Prototipe tiket konser sebagai NFT ERC-721 dengan URI metadata per token.
/// @dev Promotor membuat tiket, menunjuk petugas gerbang, dan mengubah status
///      sampai SOLD. Petugas gerbang menetapkan VALIDATED, CHECKED_IN, dan USED.
///      Pemilik NFT boleh memindahkan tiket selama status belum CHECKED_IN.
contract ConcertTicketing is ERC721URIStorage {
    // ---------------------------------------------------------------------
    // Tipe data
    // ---------------------------------------------------------------------
    enum Status {
        CREATED,     // 0
        APPROVED,    // 1
        ON_SALE,     // 2
        SOLD,        // 3
        VALIDATED,   // 4
        CHECKED_IN,  // 5
        USED         // 6
    }

    struct Ticket {
        uint256 id;
        string eventName;
        string category;
        uint256 price;
        uint256 quota;
        uint256 date;
        Status status;
        uint256 timestamp;
    }

    struct History {
        string action;
        address actor;
        address owner;
        Status status;
        uint256 timestamp;
    }

    // ---------------------------------------------------------------------
    // Penyimpanan
    // ---------------------------------------------------------------------
    address public promoter;
    mapping(address => bool) public isGate; // petugas gerbang (VALIDATED, CHECKED_IN, USED)
    uint256 private nextTokenId = 1;

    mapping(uint256 => Ticket) private tickets;
    mapping(uint256 => History[]) private histories;

    // ---------------------------------------------------------------------
    // Event
    // ---------------------------------------------------------------------
    event TicketCreated(uint256 indexed ticketId, string eventName, address indexed owner, string uri);
    event StatusUpdated(uint256 indexed ticketId, Status status, address indexed actor);
    event OwnershipTransferred(uint256 indexed ticketId, address indexed from, address indexed to);
    event PromoterChanged(address indexed oldPromoter, address indexed newPromoter);
    event GateSet(address indexed account, bool allowed);

    // ---------------------------------------------------------------------
    // Konstruktor dan modifier
    // ---------------------------------------------------------------------
    constructor() ERC721("Concert Ticket", "CTIX") {
        promoter = msg.sender;
    }

    modifier onlyPromoter() {
        require(msg.sender == promoter, "Hanya promotor");
        _;
    }

    modifier ticketExists(uint256 _ticketId) {
        require(tickets[_ticketId].id != 0, "Tiket tidak ada");
        _;
    }

    // ---------------------------------------------------------------------
    // Administrasi
    // ---------------------------------------------------------------------
    function setPromoter(address _newPromoter) external onlyPromoter {
        require(_newPromoter != address(0), "Promotor invalid");
        address oldPromoter = promoter;
        promoter = _newPromoter;
        emit PromoterChanged(oldPromoter, _newPromoter);
    }

    /// @notice Promotor menunjuk atau mencabut petugas gerbang.
    function setGate(address _account, bool _allowed) external onlyPromoter {
        require(_account != address(0), "Alamat invalid");
        isGate[_account] = _allowed;
        emit GateSet(_account, _allowed);
    }

    /// @dev Siapa yang berwenang menetapkan status tujuan tertentu.
    ///      VALIDATED, CHECKED_IN, dan USED -> petugas gerbang;
    ///      status lainnya (APPROVED, ON_SALE, SOLD) -> promotor.
    function _isAuthorizedFor(Status _target, address _account) internal view returns (bool) {
        if (uint8(_target) >= uint8(Status.VALIDATED)) return isGate[_account];
        return _account == promoter;
    }

    // ---------------------------------------------------------------------
    // 1. Membuat tiket (hanya promotor)
    // ---------------------------------------------------------------------
    function createTicket(
        string calldata _eventName,
        string calldata _category,
        uint256 _price,
        uint256 _quota,
        uint256 _date,
        string calldata _tokenURI
    ) external onlyPromoter returns (uint256) {
        require(bytes(_eventName).length > 0, "Event kosong");
        require(bytes(_category).length > 0, "Kategori kosong");
        require(_price > 0, "Harga harus > 0");
        require(_quota > 0, "Kuota harus > 0");
        require(_date > block.timestamp, "Tanggal harus di masa depan");
        require(bytes(_tokenURI).length > 0, "URI metadata kosong");

        uint256 tokenId = nextTokenId;
        nextTokenId++;

        tickets[tokenId] = Ticket({
            id: tokenId,
            eventName: _eventName,
            category: _category,
            price: _price,
            quota: _quota,
            date: _date,
            status: Status.CREATED,
            timestamp: block.timestamp
        });

        _safeMint(msg.sender, tokenId);
        _setTokenURI(tokenId, _tokenURI);
        _addHistory(tokenId, "TICKET_CREATED");
        emit TicketCreated(tokenId, _eventName, msg.sender, _tokenURI);

        return tokenId;
    }

    // ---------------------------------------------------------------------
    // 2. Mengubah status (maju satu tahap, oleh pihak yang berwenang)
    //    Urutan cek: tiket ada -> berwenang -> transisi.
    //    Promotor: APPROVED, ON_SALE, SOLD
    //    Petugas gerbang: VALIDATED, CHECKED_IN, USED
    // ---------------------------------------------------------------------
    function updateStatus(uint256 _ticketId, Status _status)
        external
        ticketExists(_ticketId)
    {
        require(_isAuthorizedFor(_status, msg.sender), "Tidak berwenang untuk status ini");

        Ticket storage ticket = tickets[_ticketId];
        require(ticket.status != Status.USED, "Tiket sudah USED");
        require(
            uint8(_status) == uint8(ticket.status) + 1,
            "Status harus maju satu tahap"
        );

        ticket.status = _status;
        ticket.timestamp = block.timestamp;
        _addHistory(_ticketId, "STATUS_UPDATED");
        emit StatusUpdated(_ticketId, _status, msg.sender);
    }

    // ---------------------------------------------------------------------
    // 3. Memindahkan kepemilikan (hanya pemilik, selama belum check-in)
    //    Urutan cek sama dengan flowchart: tiket ada -> pemilik -> status.
    // ---------------------------------------------------------------------
    function transferTicket(uint256 _ticketId, address _to)
        external
        ticketExists(_ticketId)
    {
        require(ownerOf(_ticketId) == msg.sender, "Bukan pemilik tiket");
        require(_to != address(0), "Alamat tujuan invalid");
        require(
            uint8(tickets[_ticketId].status) < uint8(Status.CHECKED_IN),
            "Tiket sudah check-in/dipakai"
        );

        _transfer(msg.sender, _to, _ticketId);
    }

    /// @dev Pengaman untuk semua jalur transfer, termasuk transferFrom dan
    ///      safeTransferFrom bawaan ERC-721. Riwayat dan event dicatat di sini
    ///      agar semua jalur transfer terekam. Jika require gagal, seluruh
    ///      transaksi dibatalkan.
    function _update(address to, uint256 tokenId, address auth)
        internal
        override
        returns (address)
    {
        address from = super._update(to, tokenId, auth);

        if (from != address(0) && to != address(0)) {
            require(
                uint8(tickets[tokenId].status) < uint8(Status.CHECKED_IN),
                "Tiket sudah check-in/dipakai"
            );
            tickets[tokenId].timestamp = block.timestamp;
            _addHistory(tokenId, "OWNERSHIP_TRANSFERRED");
            emit OwnershipTransferred(tokenId, from, to);
        }

        return from;
    }

    // ---------------------------------------------------------------------
    // 4. Melihat data tiket
    // ---------------------------------------------------------------------
    function getTicket(uint256 _ticketId)
        external
        view
        ticketExists(_ticketId)
        returns (Ticket memory ticket, address ticketOwner, string memory metadataURI)
    {
        ticket = tickets[_ticketId];
        ticketOwner = ownerOf(_ticketId);
        metadataURI = tokenURI(_ticketId);
    }

    function getOwner(uint256 _ticketId)
        external
        view
        ticketExists(_ticketId)
        returns (address)
    {
        return ownerOf(_ticketId);
    }

    function totalTickets() external view returns (uint256) {
        return nextTokenId - 1;
    }

    // ---------------------------------------------------------------------
    // 5. Melihat riwayat (dari terbaru ke terlama)
    // ---------------------------------------------------------------------
    function getHistory(uint256 _ticketId)
        external
        view
        ticketExists(_ticketId)
        returns (History[] memory)
    {
        History[] storage h = histories[_ticketId];
        uint256 len = h.length;
        History[] memory result = new History[](len);
        for (uint256 i = 0; i < len; i++) {
            result[i] = h[len - 1 - i];
        }
        return result;
    }

    // ---------------------------------------------------------------------
    // Internal
    // ---------------------------------------------------------------------
    function _addHistory(uint256 _ticketId, string memory _action) internal {
        Ticket storage ticket = tickets[_ticketId];
        histories[_ticketId].push(
            History({
                action: _action,
                actor: msg.sender,
                owner: ownerOf(_ticketId),
                status: ticket.status,
                timestamp: block.timestamp
            })
        );
    }
}