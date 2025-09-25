# Furama StayToken - Project Features Overview

## 🎯 **Project Overview**
Hệ thống voucher onchain cho khách sạn Furama, sử dụng ERC-1155 tokens trên blockchain để quản lý và sử dụng voucher.

---

## 🔐 **Authentication System**
- **OTP Authentication**: Xác thực qua email/phone OTP
- **User Profile**: Quản lý thông tin cá nhân (không auto-fill tên)
- **Session Management**: Quản lý phiên đăng nhập

---

## 🏠 **Homepage Features**
- **QR Code Scanner**: Quét QR voucher bằng camera real-time
- **Manual Code Input**: Nhập thủ công voucher code
- **Auto Claim Flow**: Tự động claim và mint voucher sau khi auth
- **Session Storage**: Lưu pending voucher codes khi chưa đăng nhập

---

## 🎫 **Voucher Management**

### **User Side**
- **Claim Vouchers**: Claim voucher qua QR code hoặc manual input
- **On-chain Minting**: Tự động mint ERC-1155 tokens khi claim
- **Wallet Integration**: Tích hợp với custodial wallet
- **Transaction Tracking**: Theo dõi tx_hash và explorer link

### **Admin Side**
- **Voucher CRUD**: Tạo, sửa, xóa voucher types
- **QR Code Export**: Xuất danh sách voucher thành PDF với QR codes
- **Balance Management**: Quản lý voucher balances

---

## 📱 **POS Scanner System**
- **Real-time QR Scanning**: Quét voucher QR codes bằng camera
- **Dual Validation**: Kiểm tra cả database và blockchain
- **Voucher Verification**: Verify token ownership on-chain
- **Redemption Process**: Xác nhận và thực hiện redemption
- **Balance Tracking**: Theo dõi balance trước/sau redemption

---

## 🔗 **Blockchain Integration**

### **ERC-1155 Client**
- **Balance Query**: Query token balance từ blockchain
- **Mint Tokens**: Mint ERC-1155 tokens cho users
- **Transaction Management**: Quản lý blockchain transactions
- **Receipt Verification**: Verify transaction receipts

### **On-chain Features**
- **Token Minting**: Tự động mint khi claim voucher
- **Balance Verification**: Verify balance trực tiếp từ blockchain
- **Transaction Logging**: Log tất cả blockchain transactions

---

## 💾 **Database Models**

### **Core Models**
- **Wallet**: Quản lý user wallets (address, address_hex)
- **VoucherType**: Định nghĩa voucher types (slug, token_id, contract)
- **VoucherBalance**: Track off-chain balances
- **VoucherTransferLog**: Log tất cả transfers/redemptions
- **OnchainTx**: Store blockchain transaction details

---

## 🎨 **User Interface**

### **Design System**
- **Responsive Design**: Mobile-first approach
- **Modern UI**: Clean, professional interface
- **Real-time Feedback**: Loading states, status messages
- **Error Handling**: User-friendly error messages

### **Key Pages**
- **Homepage**: QR scanner + manual input
- **Admin Dashboard**: Voucher management, POS scanner
- **Auth Pages**: OTP verification, profile management
- **Claim Flow**: Step-by-step voucher claiming

---

## 🔄 **Workflows**

### **Voucher Claiming Flow**
1. User quét QR code hoặc nhập manual code
2. System check authentication status
3. Nếu chưa login → redirect to OTP auth
4. Sau khi auth → auto claim và mint voucher
5. Hiển thị transaction details và explorer link

### **POS Redemption Flow**
1. Admin mở POS Scanner
2. Quét QR code voucher của customer
3. System validate voucher (database + blockchain)
4. Hiển thị voucher details và validation status
5. Admin xác nhận redemption
6. System giảm balance và log transaction

### **QR Code Generation**
- **Format**: `voucher:slug:wallet_address`
- **PDF Export**: Generate PDF với QR codes cho printing
- **Caching**: Cache QR images để tối ưu performance

---

## 🛠 **Technical Stack**
- **Backend**: Django 5.0.6
- **Frontend**: Alpine.js, Tailwind CSS
- **Blockchain**: Web3.py, ERC-1155
- **QR Codes**: jsQR, qrcode library
- **PDF Generation**: ReportLab
- **Database**: SQLite (development)

---

## 📋 **Recent Updates**

### **v1.0 - Initial Release**
- ✅ Basic authentication system
- ✅ Voucher claiming with QR scanning
- ✅ On-chain minting integration
- ✅ Admin voucher management

### **v1.1 - POS Scanner**
- ✅ Admin POS scanner interface
- ✅ Real-time QR code scanning
- ✅ Dual validation (database + blockchain)
- ✅ Voucher redemption workflow
- ✅ Transaction logging

### **v1.2 - Enhanced UX**
- ✅ Fixed PDF export for Windows
- ✅ Improved QR scanning flow
- ✅ Better error handling
- ✅ Session storage for pending claims

---

## 🚀 **Future Enhancements**
- [ ] Multi-merchant support
- [ ] Advanced analytics dashboard
- [ ] Mobile app integration
- [ ] Batch voucher operations
- [ ] Advanced reporting features

---

*Last updated: September 25, 2025*
