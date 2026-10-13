// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";

/// @title ConcertTicketing
/// @notice Prototype tiket konser sebagai NFT ERC-721 dengan URI metadata per token.
contract ConcertTicketing is ERC721URIStorage {
    constructor() ERC721("Concert Ticket", "CTIX") {
        promoter = msg.sender;
    }

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
    uint256 private nextTokenId = 1;

    mapping(uint256 => Ticket) public tickets;
    mapping(uint256 => History[]) private histories;

    event TicketCreated(uint256 indexed ticketId, string eventName, address indexed owner, string tokenURI);
    event StatusUpdated(uint256 indexed ticketId, Status status, address indexed actor);
    event OwnershipTransferred(uint256 indexed ticketId, address indexed from, address indexed to);
    event PromoterChanged(address indexed oldPromoter, address indexed newPromoter);

    modifier onlyPromoter() {
        require(msg.sender == promoter, "Hanya promotor");
        _;
    }

    function setPromoter(address _newPromoter) external onlyPromoter {
        require(_newPromoter != address(0), "Promotor invalid");
        address oldPromoter = promoter;
        promoter = _newPromoter;
        emit PromoterChanged(oldPromoter, _newPromoter);
    }

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

    function updateStatus(uint256 _ticketId, Status _status) external onlyPromoter {
        Ticket storage ticket = tickets[_ticketId];
        require(ticket.id != 0, "Tiket tidak ada");
        require(uint8(_status) == uint8(ticket.status) + 1, "Status harus maju satu tahap");

        ticket.status = _status;
        ticket.timestamp = block.timestamp;
        _addHistory(_ticketId, "STATUS_UPDATED");
        emit StatusUpdated(_ticketId, _status, msg.sender);
    }

    function _update(address to, uint256 tokenId, address auth)
        internal
        override
        returns (address from)
    {
        from = _ownerOf(tokenId);
        if (from != address(0) && to != address(0)) {
            require(
                uint8(tickets[tokenId].status) < uint8(Status.CHECKED_IN),
                "Tiket sudah check-in/tidak dapat ditransfer"
            );
        }

        from = super._update(to, tokenId, auth);
        if (from != address(0) && to != address(0)) {
            tickets[tokenId].timestamp = block.timestamp;
            _addHistory(tokenId, "OWNERSHIP_TRANSFERRED");
            emit OwnershipTransferred(tokenId, from, to);
        }
    }

    function getOwner(uint256 _ticketId) public view returns (address) {
        require(tickets[_ticketId].id != 0, "Tiket tidak ada");
        return ownerOf(_ticketId);
    }

    function getTicket(uint256 _ticketId)
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
            uint256 timestamp,
            string memory metadataURI
        )
    {
        Ticket memory ticket = tickets[_ticketId];
        require(ticket.id != 0, "Tiket tidak ada");
        return (
            ticket.eventName,
            ticket.category,
            ticket.price,
            ownerOf(_ticketId),
            ticket.status,
            ticket.quota,
            ticket.date,
            ticket.timestamp,
            tokenURI(_ticketId)
        );
    }

    function getHistory(uint256 _ticketId) external view returns (History[] memory) {
        require(tickets[_ticketId].id != 0, "Tiket tidak ada");
        History[] storage h = histories[_ticketId];
        uint256 len = h.length;
        History[] memory result = new History[](len);
        for (uint256 i = 0; i < len; i++) {
            result[i] = h[len - 1 - i];
        }
        return result;
    }

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
