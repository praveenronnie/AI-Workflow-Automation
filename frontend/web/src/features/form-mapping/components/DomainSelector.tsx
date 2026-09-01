import { useStore } from '@/store/useStore';
import { useState, useEffect } from 'react';

export interface DomainOption {
  id: string;
  name: string;
  description?: string;
}

interface DomainSelectorProps {
  onDomainChange?: (domain: string) => void;
}

/**
 * Domain selector.
 *
 * The list of available domains is sourced from the backend via the message
 * bus (background service worker -> GET /domains), not a relative fetch.
 * This makes the extension domain-agnostic: the domain slugs are discovery
 * data, never hardcoded platform names.
 */
export function DomainSelector(props: DomainSelectorProps = {}) {
  const store = useStore();
  const domain = store.domain;
  const setDomain = store.setDomain;
  const storeDomains = store.domains;
  const fetchDomains = store.fetchDomains;
  const [loading, setLoading] = useState(storeDomains.length === 0);

  // Populate domains from the backend on mount (idempotent if already loaded).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (storeDomains.length > 0) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        await fetchDomains();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setDomain(next);
    if (props.onDomainChange) props.onDomainChange(next);
  };

  if (loading) {
    return (
      <div className='flex items-center space-x-2 px-3 py-2'>
        <span className='text-sm text-muted-foreground'>Loading domains...</span>
      </div>
    );
  }

  const options = storeDomains;

  return (
    <div className='flex items-center space-x-2 px-3 py-2'>
      <span className='text-xs text-muted-foreground'>Domain:</span>
      <select
        value={domain}
        onChange={handleChange}
        className='text-xs rounded-md border px-2 py-1 bg-background'
      >
        {options.length === 0 ? (
          <option value={domain}>{domain.replace(/_/g, ' ')}</option>
        ) : (
          options.map((d) => (
            <option key={d.id} value={d.name}>
              {d.name.replace(/_/g, ' ')}
            </option>
          ))
        )}
      </select>
    </div>
  );
}
