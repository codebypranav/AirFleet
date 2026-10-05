"use client";

import { useCallback, useEffect, useState } from 'react';

type State<T> = { data: T | null; error: string; loading: boolean };

/**
 * Loads `load()` on mount and whenever `key` changes. `reload()` fetches again;
 * `setData` lets a page patch the cached result after a mutation.
 */
export function useApi<T>(load: () => Promise<T>, key: string = '') {
    const [state, setState] = useState<State<T>>({ data: null, error: '', loading: true });
    const [version, setVersion] = useState(0);
    const [loadedFor, setLoadedFor] = useState({ key, version });

    // Show the spinner again when the inputs change, without a synchronous setState in the effect.
    if (loadedFor.key !== key || loadedFor.version !== version) {
        setLoadedFor({ key, version });
        setState((prev) => ({ ...prev, loading: true, error: '' }));
    }

    useEffect(() => {
        let ignore = false;
        load()
            .then((data) => {
                if (!ignore) setState({ data, error: '', loading: false });
            })
            .catch((error: unknown) => {
                if (!ignore) setState((prev) => ({ ...prev, error: error instanceof Error ? error.message : String(error), loading: false }));
            });
        return () => {
            ignore = true;
        };
        // `load` is recreated every render; `key` is what identifies the request.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key, version]);

    const reload = useCallback(() => setVersion((v) => v + 1), []);
    const setData = useCallback((update: (data: T | null) => T | null) => setState((prev) => ({ ...prev, data: update(prev.data) })), []);

    return { ...state, reload, setData };
}
