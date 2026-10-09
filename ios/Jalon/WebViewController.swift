/*
 * Jalon — NCN ⇄ GSI Dönüştürücü (iOS)
 * Telif Hakkı (c) 2026 Egemen Çalıkoğlu. Tüm hakları saklıdır.
 *
 * Android'deki ile aynı sayfayı (index.html) açar. Sayfa, Android'de window.AndroidBridge
 * üzerinden dosya seçme, kaydetme ve kopyalama yapıyor; iOS'ta aynı adla bir köprü tanımlanır,
 * böylece sayfanın kendisi değişmeden iki platformda da çalışır.
 */
import UIKit
import WebKit
import UniformTypeIdentifiers

final class WebViewController: UIViewController, WKNavigationDelegate, WKScriptMessageHandler, UIDocumentPickerDelegate {

    private static let background = UIColor(red: 0x0E / 255, green: 0x0E / 255, blue: 0x0D / 255, alpha: 1)

    private var web: WKWebView!
    private var pageReady = false
    private var pendingFiles: [URL] = []
    private var exportFile: URL?
    private var exportName = ""

    // Sayfadaki window.AndroidBridge çağrılarını iOS'a yönlendirir
    private static let bridgeScript = """
    window.AndroidBridge = {
      pickFiles: function () { window.webkit.messageHandlers.jalon.postMessage({ op: 'pick' }); },
      saveFile: function (name, data) { window.webkit.messageHandlers.jalon.postMessage({ op: 'save', name: String(name), data: String(data) }); },
      copy: function (text) { window.webkit.messageHandlers.jalon.postMessage({ op: 'copy', text: String(text) }); }
    };
    """

    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    override func loadView() {
        let content = WKUserContentController()
        content.addUserScript(WKUserScript(source: Self.bridgeScript, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        content.add(WeakMessageHandler(self), name: "jalon")

        let config = WKWebViewConfiguration()
        config.userContentController = content
        config.dataDetectorTypes = []

        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.isOpaque = false
        web.backgroundColor = Self.background
        web.scrollView.backgroundColor = Self.background
        // Sayfa güvenli alan boşluklarını kendisi veriyor (viewport-fit=cover + env(safe-area-inset-*))
        web.scrollView.contentInsetAdjustmentBehavior = .never
        web.allowsLinkPreview = false
        web.translatesAutoresizingMaskIntoConstraints = false

        // Sayfa saat/pil şeridinin altından başlar (kaydırınca içerik o şeridin arkasından geçmesin);
        // şerit Android'deki gibi düz koyu renkte kalır. Alt kenar tam ekran: sayfa alt boşluğunu kendisi verir.
        let root = UIView()
        root.backgroundColor = Self.background
        root.addSubview(web)
        NSLayoutConstraint.activate([
            web.topAnchor.constraint(equalTo: root.safeAreaLayoutGuide.topAnchor),
            web.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            web.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            web.bottomAnchor.constraint(equalTo: root.bottomAnchor),
        ])
        view = root
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        guard let page = Bundle.main.url(forResource: "index", withExtension: "html") else { return }
        web.loadFileURL(page, allowingReadAccessTo: page.deletingLastPathComponent())
    }

    // MARK: - Sayfa yüklendi / dış bağlantılar

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        pageReady = true
        flushPendingFiles()
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { return decisionHandler(.cancel) }
        if url.isFileURL || url.scheme == "about" || url.scheme == "blob" || url.scheme == "data" {
            return decisionHandler(.allow)
        }
        // Gizlilik politikası vb. bağlantılar Safari'de açılır
        if action.navigationType == .linkActivated || action.targetFrame == nil {
            UIApplication.shared.open(url)
            return decisionHandler(.cancel)
        }
        decisionHandler(.allow)
    }

    // MARK: - Köprü

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any], let op = body["op"] as? String else { return }
        switch op {
        case "pick":
            pickFiles()
        case "save":
            saveFile(name: body["name"] as? String ?? "jalon.txt", data: body["data"] as? String ?? "")
        case "copy":
            UIPasteboard.general.string = body["text"] as? String ?? ""
        default:
            break
        }
    }

    private func pickFiles() {
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.item], asCopy: true)
        picker.allowsMultipleSelection = true
        picker.delegate = self
        present(picker, animated: true)
    }

    private func saveFile(name: String, data: String) {
        let safeName = name.replacingOccurrences(of: "/", with: "-").replacingOccurrences(of: ":", with: "-")
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let file = dir.appendingPathComponent(safeName.isEmpty ? "jalon.txt" : safeName)
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try data.write(to: file, atomically: true, encoding: .utf8)
        } catch {
            toast("Dosya yazılamadı: \(error.localizedDescription)")
            return
        }
        exportFile = file
        exportName = file.lastPathComponent
        let picker = UIDocumentPickerViewController(forExporting: [file], asCopy: true)
        picker.delegate = self
        present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        if exportFile != nil {
            toast("\(exportName) kaydedildi.")
            cleanupExport()
        } else {
            pendingFiles.append(contentsOf: urls)
            flushPendingFiles()
        }
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        if exportFile != nil {
            toast("Kaydetme iptal edildi.")
            cleanupExport()
        }
    }

    private func cleanupExport() {
        if let f = exportFile { try? FileManager.default.removeItem(at: f.deletingLastPathComponent()) }
        exportFile = nil
    }

    // MARK: - Dosyaları sayfaya ver

    func openIncoming(_ url: URL) {
        pendingFiles.append(url)
        flushPendingFiles()
    }

    private func flushPendingFiles() {
        guard pageReady, !pendingFiles.isEmpty else { return }
        let files = pendingFiles
        pendingFiles.removeAll()
        for url in files {
            do {
                let text = try readText(url)
                callPage("window.__addFileFromApp", [url.lastPathComponent, text])
            } catch {
                toast("Dosya okunamadı: \(url.lastPathComponent)")
            }
        }
    }

    private func readText(_ url: URL) throws -> String {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        let data = try Data(contentsOf: url)
        if let s = String(data: data, encoding: .utf8) { return s }
        // Netcad dosyaları çoğunlukla Windows Türkçe kod sayfasındadır (windows-1254)
        let cp1254 = String.Encoding(rawValue: CFStringConvertEncodingToNSStringEncoding(
            CFStringEncoding(CFStringEncodings.windowsLatin5.rawValue)))
        return String(data: data, encoding: cp1254) ?? String(decoding: data, as: UTF8.self)
    }

    private func toast(_ message: String) {
        callPage("window.__toast", [message])
    }

    private func callPage(_ function: String, _ args: [String]) {
        guard let json = try? JSONSerialization.data(withJSONObject: args),
              let list = String(data: json, encoding: .utf8) else { return }
        web.evaluateJavaScript("\(function) && \(function).apply(null, \(list))", completionHandler: nil)
    }
}

/// WKUserContentController betik işleyicisini güçlü tutar; döngü olmasın diye araya zayıf bir aracı konur.
private final class WeakMessageHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.userContentController(controller, didReceive: message)
    }
}
