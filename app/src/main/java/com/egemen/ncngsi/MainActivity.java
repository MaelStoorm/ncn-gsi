/*
 * NCN ⇄ GSI Dönüştürücü
 * Telif Hakkı (c) 2026 Egemen Çalıkoğlu. Tüm hakları saklıdır.
 */
package com.egemen.ncngsi;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.res.Configuration;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.util.DisplayMetrics;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

import androidx.webkit.WebViewAssetLoader;

import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.AdSize;
import com.google.android.gms.ads.AdView;
import com.google.android.gms.ads.MobileAds;
import com.google.android.ump.ConsentInformation;
import com.google.android.ump.ConsentRequestParameters;
import com.google.android.ump.UserMessagingPlatform;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {

    private static final String START_URL = "https://appassets.androidplatform.net/assets/index.html";
    private static final int REQ_OPEN = 1;
    private static final int REQ_SAVE = 2;

    private WebView web;
    private FrameLayout adContainer;
    private AdView adView;
    private WebViewAssetLoader assetLoader;
    private ConsentInformation consentInformation;
    private final AtomicBoolean adsStarted = new AtomicBoolean(false);

    private boolean pageReady = false;
    private final List<Uri> pendingUris = new ArrayList<>();
    private String pendingSaveData;
    private String pendingSaveName;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        boolean night = (getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        int bg = Color.parseColor("#0E0E0D");

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(bg);

        web = new WebView(this);
        web.setBackgroundColor(bg);
        root.addView(web, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        adContainer = new FrameLayout(this);
        root.addView(adContainer, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        setContentView(root);
        // Sistem çubuklarının arkasına çiz, boşluğu kendimiz verelim (tüm sürümlerde aynı davranış)
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
        } else {
            int flags = View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION;
            root.setSystemUiVisibility(flags);
        }
        applySystemBarInsets(root);
        setupWebView();
        collectIntentUris(getIntent());
        web.loadUrl(START_URL);
        requestConsentThenAds();
    }

    /* ---------------- Kenardan kenara ekran (Android 15+) ---------------- */
    private void applySystemBarInsets(View root) {
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                Insets i = insets.getInsets(WindowInsets.Type.systemBars()
                        | WindowInsets.Type.displayCutout());
                v.setPadding(i.left, i.top, i.right, i.bottom);
            } else {
                v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
    }

    /* ---------------- WebView ---------------- */
    private void setupWebView() {
        assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setSupportZoom(false);

        web.addJavascriptInterface(new Bridge(), "AndroidBridge");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return assetLoader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if ("appassets.androidplatform.net".equals(u.getHost())) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (Exception ignored) { }
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                pageReady = true;
                flushPendingUris();
            }
        });
    }

    /** Sayfadaki JavaScript'in çağırdığı köprü: window.AndroidBridge */
    private class Bridge {
        @JavascriptInterface
        public void pickFiles() {
            runOnUiThread(() -> {
                Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try {
                    startActivityForResult(i, REQ_OPEN);
                } catch (Exception e) {
                    toastJs("Dosya seçici açılamadı.");
                }
            });
        }

        @JavascriptInterface
        public void saveFile(String name, String data) {
            runOnUiThread(() -> {
                pendingSaveName = name;
                pendingSaveData = data;
                Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                // octet-stream: Android'in adın sonuna .txt eklemesini önler (.GSI / .NCN korunur)
                i.setType("application/octet-stream");
                i.putExtra(Intent.EXTRA_TITLE, name);
                try {
                    startActivityForResult(i, REQ_SAVE);
                } catch (Exception e) {
                    toastJs("Kaydetme ekranı açılamadı.");
                }
            });
        }

        @JavascriptInterface
        public void copy(String text) {
            runOnUiThread(() -> {
                ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("GSI/NCN", text));
            });
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_OPEN) {
            if (resultCode != RESULT_OK || data == null) return;
            if (data.getClipData() != null) {
                ClipData cd = data.getClipData();
                for (int k = 0; k < cd.getItemCount(); k++) pendingUris.add(cd.getItemAt(k).getUri());
            } else if (data.getData() != null) {
                pendingUris.add(data.getData());
            }
            flushPendingUris();
        } else if (requestCode == REQ_SAVE) {
            String payload = pendingSaveData, name = pendingSaveName;
            pendingSaveData = null;
            if (resultCode != RESULT_OK || data == null || data.getData() == null || payload == null) {
                toastJs("Kaydetme iptal edildi.");
                return;
            }
            try (OutputStream os = getContentResolver().openOutputStream(data.getData(), "wt")) {
                if (os == null) throw new Exception("stream");
                os.write(payload.getBytes(StandardCharsets.UTF_8));
                toastJs(displayName(data.getData(), name) + " kaydedildi.");
            } catch (Exception e) {
                toastJs("Dosya yazılamadı: " + e.getMessage());
            }
        }
    }

    /* ---------------- Dışarıdan gelen dosyalar ---------------- */
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        collectIntentUris(intent);
        flushPendingUris();
    }

    private void collectIntentUris(Intent intent) {
        if (intent == null || intent.getAction() == null) return;
        String a = intent.getAction();
        if (Intent.ACTION_VIEW.equals(a) && intent.getData() != null) {
            pendingUris.add(intent.getData());
        } else if (Intent.ACTION_SEND.equals(a)) {
            Uri u = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (u != null) pendingUris.add(u);
        } else if (Intent.ACTION_SEND_MULTIPLE.equals(a)) {
            ArrayList<Uri> list = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (list != null) pendingUris.addAll(list);
        }
    }

    private void flushPendingUris() {
        if (!pageReady || pendingUris.isEmpty()) return;
        List<Uri> uris = new ArrayList<>(pendingUris);
        pendingUris.clear();
        for (Uri u : uris) {
            try {
                String text = readText(u);
                String name = displayName(u, "dosya.txt");
                web.evaluateJavascript("window.__addFileFromApp(" + JSONObject.quote(name) + ","
                        + JSONObject.quote(text) + ")", null);
            } catch (Exception e) {
                toastJs("Dosya okunamadı: " + e.getMessage());
            }
        }
    }

    private String readText(Uri uri) throws Exception {
        byte[] bytes;
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) throw new Exception("açılamadı");
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            bytes = bo.toByteArray();
        }
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException e) {
            // Netcad dosyaları çoğunlukla Windows Türkçe kod sayfasındadır
            return new String(bytes, Charset.forName("windows-1254"));
        }
    }

    private String displayName(Uri uri, String fallback) {
        try (Cursor c = getContentResolver().query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                String n = c.getString(0);
                if (n != null && !n.isEmpty()) return n;
            }
        } catch (Exception ignored) { }
        String last = uri.getLastPathSegment();
        return last != null ? last : fallback;
    }

    private void toastJs(String msg) {
        if (web == null) return;
        web.post(() -> web.evaluateJavascript(
                "window.__toast&&window.__toast(" + JSONObject.quote(msg) + ")", null));
    }

    /* ---------------- Reklam: önce izin (UMP), sonra banner ---------------- */
    private void requestConsentThenAds() {
        consentInformation = UserMessagingPlatform.getConsentInformation(this);
        ConsentRequestParameters params = new ConsentRequestParameters.Builder().build();
        consentInformation.requestConsentInfoUpdate(this, params,
                () -> UserMessagingPlatform.loadAndShowConsentFormIfRequired(this, formError -> {
                    if (consentInformation.canRequestAds()) startAds();
                }),
                requestError -> {
                    if (consentInformation.canRequestAds()) startAds();
                });
        if (consentInformation.canRequestAds()) startAds();
    }

    private void startAds() {
        if (adsStarted.getAndSet(true)) return;
        new Thread(() -> {
            MobileAds.initialize(this, status -> { });
            runOnUiThread(this::loadBanner);
        }).start();
    }

    private void loadBanner() {
        adView = new AdView(this);
        adView.setAdUnitId(getString(R.string.admob_banner_id));
        DisplayMetrics dm = getResources().getDisplayMetrics();
        int widthDp = (int) (dm.widthPixels / dm.density);
        adView.setAdSize(AdSize.getCurrentOrientationAnchoredAdaptiveBannerAdSize(this, widthDp));
        adContainer.removeAllViews();
        adContainer.addView(adView);
        adView.loadAd(new AdRequest.Builder().build());
    }

    @Override
    protected void onPause() {
        if (adView != null) adView.pause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (adView != null) adView.resume();
    }

    @Override
    protected void onDestroy() {
        if (adView != null) adView.destroy();
        if (web != null) web.destroy();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
