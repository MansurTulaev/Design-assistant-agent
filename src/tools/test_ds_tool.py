from .ds_tool import DesignSystemParser, scan_design_system

if __name__ == "__main__":
    parser = DesignSystemParser()
    components = parser.scan_directory(r"C:\Users\Mans\Documents\AI DEV Hackathon\react-design-system\components")

    print(f"Всего компонентов: {len(components)}")
    for c in components:
        print(f"- {c.name} ({c.file_path})")
        for p in c.props:
            print(f"    {p.name}: {p.type}, required={p.required}")
