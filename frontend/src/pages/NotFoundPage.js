import { useEffect, useState } from 'react';
import Lottie from 'lottie-react';
import { useAppSettings } from '@/contexts/AppSettingsContext';

const NotFoundPage = () => {
  const { settings } = useAppSettings();

  const [animationData, setAnimationData] = useState(null);
  const [animationError, setAnimationError] = useState(false);

  const enabled = settings?.not_found_lottie_enabled !== false;
  const animationUrl = settings?.not_found_lottie_url;

  useEffect(() => {
    let cancelled = false;

    if (!enabled || !animationUrl) {
      setAnimationData(null);
      return undefined;
    }

    setAnimationError(false);
    setAnimationData(null);

    fetch(animationUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load animation: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        if (!cancelled) {
          setAnimationData(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAnimationError(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, animationUrl]);

  useEffect(() => {
    const title = settings?.site_title || settings?.brand_name || 'OfficeFlow';
    document.title = `Page Not Found | ${title}`;
  }, [settings]);

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#09090B] flex items-center justify-center px-4 sm:px-6">
      {enabled && animationData && !animationError && (
        <div className="w-full max-w-[1000px]">
          <Lottie
            animationData={animationData}
            loop
            autoplay
            className="w-full h-auto"
          />
        </div>
      )}
    </div>
  );
};

export default NotFoundPage;
