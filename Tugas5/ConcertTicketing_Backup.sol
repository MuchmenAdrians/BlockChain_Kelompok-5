// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract ConcertTicketing {

    enum Status {
        CREATED,
        APPROVED,
        ON_SALE,
        SOLD,
        VALIDATED,
        CHECKED_IN,
        USED
    }

    struct Ticket {
        uint256 id;
        string eventName;
        string category;
        uint256 price;
        uint256 quota;
        uint256 date;
        address owner;
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

    address public promoter;
    mapping(address => bool) public isGate; // petugas gerbang (VALIDATED, CHECKED_IN, USED)

    uint256 private nextTicketId = 1;

    mapping(uint256 => Ticket) public tickets;
    mapping(uint256 => History[]) private histories;

    event GateSet(address indexed account, bool allowed);

    constructor() {
        promoter = msg.sender;
    }

    modifier onlyPromoter() {
        require(msg.sender == promoter, "Hanya promotor");
        _;
    }

    /// @notice Promotor menunjuk atau mencabut petugas gerbang.
    function setGate(address _account, bool _allowed) external onlyPromoter {
        require(_account != address(0), "Alamat invalid");
        isGate[_account] = _allowed;
        emit GateSet(_account, _allowed);
    }

    /// @dev VALIDATED, CHECKED_IN, dan USED -> petugas gerbang;
    ///      status lainnya (APPROVED, ON_SALE, SOLD) -> promotor.
    function _isAuthorizedFor(Status _target, address _account) internal view returns (bool) {
        if (uint8(_target) >= uint8(Status.VALIDATED)) return isGate[_account];
        return _account == promoter;
    }

    event TicketCreated(
        uint256 indexed ticketId,
        string eventName,
        address indexed owner
    );

    event StatusUpdated(
        uint256 indexed ticketId,
        Status status,
        address indexed actor
    );

    event OwnershipTransferred(
        uint256 indexed ticketId,
        address indexed from,
        address indexed to
    );

    // =====================================================
    // 1. MEMBUAT TIKET
    // =====================================================
    function createTicket(
        string calldata _eventName,
        string calldata _category,
        uint256 _price,
        uint256 _quota,
        uint256 _date
    ) external onlyPromoter {

        require(bytes(_eventName).length > 0, "Event kosong");
        require(bytes(_category).length > 0, "Kategori kosong");
        require(_price > 0, "Harga harus > 0");
        require(_quota > 0, "Kuota harus > 0");
        require(_date > 0, "Tanggal kosong");

        uint256 ticketId = nextTicketId;

        tickets[ticketId] = Ticket({
            id: ticketId,
            eventName: _eventName,
            category: _category,
            price: _price,
            quota: _quota,
            date: _date,
            owner: msg.sender,
            status: Status.CREATED,
            timestamp: block.timestamp
        });

        nextTicketId++;

        _addHistory(ticketId, "TICKET_CREATED");

        emit TicketCreated(ticketId, _eventName, msg.sender);
    }

    // =====================================================
    // 2. MENGUBAH STATUS
    // =====================================================
    function updateStatus(
        uint256 _ticketId,
        Status _status
    ) external {

        Ticket storage ticket = tickets[_ticketId];

        require(ticket.id != 0, "Tiket tidak ada");
        require(_isAuthorizedFor(_status, msg.sender), "Tidak berwenang untuk status ini");
        require(
            uint8(_status) == uint8(ticket.status) + 1,
            "Status invalid"
        );

        ticket.status = _status;
        ticket.timestamp = block.timestamp;

        _addHistory(_ticketId, "STATUS_UPDATED");

        emit StatusUpdated(_ticketId, _status, msg.sender);
    }

    // =====================================================
    // 3. MEMINDAHKAN KEPEMILIKAN
    // =====================================================
    function transferTicket(
        uint256 _ticketId,
        address _newOwner
    ) external {

        Ticket storage ticket = tickets[_ticketId];

        require(ticket.id != 0, "Tiket tidak ada");
        require(ticket.owner == msg.sender, "Bukan pemilik");
        require(_newOwner != address(0), "Pemilik baru invalid");

        address oldOwner = ticket.owner;

        ticket.owner = _newOwner;
        ticket.timestamp = block.timestamp;

        _addHistory(_ticketId, "OWNERSHIP_TRANSFERRED");

        emit OwnershipTransferred(_ticketId, oldOwner, _newOwner);
    }

    // =====================================================
    // 4. MELIHAT DATA TIKET
    // =====================================================
    function getTicket(
        uint256 _ticketId
    )
        external
        view
        returns (
            string memory eventName,
            string memory category,
            uint256 price,
            address owner,
            Status status,
            uint256 quota,
            uint256 date,
            uint256 timestamp
        )
    {
        Ticket memory ticket = tickets[_ticketId];

        require(ticket.id != 0, "Tiket tidak ada");

        return (
            ticket.eventName,
            ticket.category,
            ticket.price,
            ticket.owner,
            ticket.status,
            ticket.quota,
            ticket.date,
            ticket.timestamp
        );
    }

    // =====================================================
    // 5. MELIHAT RIWAYAT (terbaru -> terlama)
    // =====================================================
    function getHistory(
        uint256 _ticketId
    ) external view returns (History[] memory) {

        require(tickets[_ticketId].id != 0, "Tiket tidak ada");

        History[] storage h = histories[_ticketId];
        uint256 len = h.length;
        History[] memory result = new History[](len);

        for (uint256 i = 0; i < len; i++) {
            result[i] = h[len - 1 - i];
        }

        return result;
    }

    // =====================================================
    // INTERNAL
    // =====================================================
    function _addHistory(uint256 _ticketId, string memory _action) internal {
        Ticket storage ticket = tickets[_ticketId];

        histories[_ticketId].push(
            History({
                action: _action,
                actor: msg.sender,
                owner: ticket.owner,
                status: ticket.status,
                timestamp: block.timestamp
            })
        );
    }
}