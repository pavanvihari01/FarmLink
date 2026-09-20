import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    google?: {
      translate?: {
        TranslateElement: new (
          options: {
            pageLanguage: string;
            includedLanguages: string;
            autoDisplay: boolean;
          },
          element: string
        ) => void;
      };
    };
    googleTranslateElementInit?: () => void;
  }
}

const LANGUAGES = [
  ['en', 'English'],
  ['te', 'తెలుగు'],
  ['hi', 'हिन्दी'],
  ['ta', 'தமிழ்'],
  ['kn', 'ಕನ್ನಡ'],
  ['ml', 'മലയാളം'],
  ['mr', 'मराठी'],
  ['bn', 'বাংলা'],
  ['gu', 'ગુજરાતી'],
  ['pa', 'ਪੰਜਾਬੀ'],
  ['or', 'ଓଡ଼ିଆ'],
  ['as', 'অসমীয়া'],
  ['ur', 'اردو'],
].map(([code]) => code).join(',');

export default function LanguageTranslator() {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;

    const init = () => {
      if (
        window.google?.translate?.TranslateElement &&
        !initialized.current
      ) {
        initialized.current = true;

        new window.google.translate.TranslateElement(
          {
            pageLanguage: 'en',
            includedLanguages: LANGUAGES,
            autoDisplay: false,
          },
          'google_translate_element'
        );
      }
    };

    window.googleTranslateElementInit = init;

    if (
      document.querySelector(
        'script[src*="translate.google.com/translate_a/element.js"]'
      )
    ) {
      init();
      return;
    }

    const script = document.createElement('script');
    script.src =
      'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    script.async = true;
    document.body.appendChild(script);

    return () => {
      window.googleTranslateElementInit = undefined;
    };
  }, []);

  return (
    <div className="language-translator">
      <span aria-hidden="true">🌐</span>
      <div id="google_translate_element" />
    </div>
  );
}
