import "@testing-library/jest-dom/vitest";

// jsdom has no scrollIntoView. Behave like current Chrome, which returns a Promise:
// that difference crashed the Ask panel once (effect returned it as a "cleanup").
Element.prototype.scrollIntoView = function () { return Promise.resolve() as unknown as void; };
