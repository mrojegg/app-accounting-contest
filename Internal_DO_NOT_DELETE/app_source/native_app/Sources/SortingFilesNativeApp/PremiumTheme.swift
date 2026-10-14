import SwiftUI

enum AppPalette {
    static let canvas = Color(red: 0.949, green: 0.957, blue: 0.961)
    static let canvasTop = canvas
    static let canvasBottom = Color(red: 0.937, green: 0.949, blue: 0.957)
    static let panel = Color.white
    static let panelRaised = Color(red: 0.980, green: 0.984, blue: 0.988)
    static let panelMuted = Color(red: 0.933, green: 0.949, blue: 0.961)
    static let stroke = Color(red: 0.863, green: 0.886, blue: 0.910)
    static let strongStroke = Color(red: 0.714, green: 0.761, blue: 0.804)
    static let textPrimary = Color(red: 0.090, green: 0.129, blue: 0.169)
    static let textSecondary = Color(red: 0.373, green: 0.420, blue: 0.471)
    static let accent = Color(red: 0.122, green: 0.369, blue: 0.341)
    static let accentPressed = Color(red: 0.086, green: 0.294, blue: 0.275)
    static let accentMuted = Color(red: 0.894, green: 0.941, blue: 0.929)
    static let info = Color(red: 0.173, green: 0.412, blue: 0.671)
    static let infoMuted = Color(red: 0.910, green: 0.945, blue: 0.984)
    static let success = Color(red: 0.184, green: 0.490, blue: 0.357)
    static let successMuted = Color(red: 0.902, green: 0.957, blue: 0.929)
    static let warning = Color(red: 0.651, green: 0.416, blue: 0.071)
    static let warningMuted = Color(red: 0.992, green: 0.953, blue: 0.875)
    static let destructive = Color(red: 0.706, green: 0.137, blue: 0.094)
    static let destructiveMuted = Color(red: 0.992, green: 0.925, blue: 0.914)
    static let sidebar = Color(red: 0.063, green: 0.133, blue: 0.129)
    static let sidebarRaised = Color(red: 0.086, green: 0.176, blue: 0.169)
    static let sidebarSelection = Color(red: 0.118, green: 0.251, blue: 0.235)
    static let sidebarText = Color.white
    static let sidebarTextSecondary = Color.white.opacity(0.62)
    static let sidebarStroke = Color.white.opacity(0.10)
    static let shadow = Color.black.opacity(0.055)
}

struct AppChromeBackground: View {
    var body: some View {
        AppPalette.canvas
            .ignoresSafeArea()
    }
}

struct AppCardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(AppPalette.panel)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(AppPalette.stroke, lineWidth: 1)
                    )
            )
            .shadow(color: AppPalette.shadow, radius: 4, x: 0, y: 1)
    }
}

struct AppInsetSurfaceModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(AppPalette.panelRaised)
                    .overlay(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .stroke(AppPalette.stroke, lineWidth: 1)
                    )
            )
    }
}

extension View {
    func appCard() -> some View {
        modifier(AppCardModifier())
    }

    func appInsetSurface() -> some View {
        modifier(AppInsetSurfaceModifier())
    }

    func premiumSettingsPanel() -> some View {
        modifier(PremiumSettingsPanelModifier())
    }
}

struct PremiumSettingsPanelModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(AppPalette.panel)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(AppPalette.stroke, lineWidth: 1)
                    )
            )
            .shadow(color: AppPalette.shadow, radius: 3, x: 0, y: 1)
    }
}

struct AppSectionHeader: View {
    let title: String
    let systemImage: String?

    init(_ title: String, systemImage: String? = nil) {
        self.title = title
        self.systemImage = systemImage
    }

    @ViewBuilder
    var body: some View {
        if let systemImage {
            Label(title, systemImage: systemImage)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(AppPalette.textPrimary)
        } else {
            Text(title)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(AppPalette.textPrimary)
        }
    }
}

enum AppPillTone {
    case neutral
    case accent
    case info
    case success
    case warning
    case danger

    var foreground: Color {
        switch self {
        case .neutral: return AppPalette.textSecondary
        case .accent: return AppPalette.accent
        case .info: return AppPalette.info
        case .success: return AppPalette.success
        case .warning: return AppPalette.warning
        case .danger: return AppPalette.destructive
        }
    }

    var background: Color {
        switch self {
        case .neutral: return AppPalette.panelMuted
        case .accent: return AppPalette.accentMuted
        case .info: return AppPalette.infoMuted
        case .success: return AppPalette.successMuted
        case .warning: return AppPalette.warningMuted
        case .danger: return AppPalette.destructiveMuted
        }
    }
}

struct AppPill: View {
    let title: String
    let systemImage: String
    var tone: AppPillTone = .neutral

    var body: some View {
        Label(title, systemImage: systemImage)
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(tone.foreground)
            .lineLimit(1)
            .padding(.horizontal, 9)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(tone.background)
                    .overlay(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .stroke(tone.foreground.opacity(0.20), lineWidth: 1)
                    )
            )
    }
}

struct AppPrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(Color.white)
            .padding(.horizontal, 15)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(configuration.isPressed ? AppPalette.accentPressed : AppPalette.accent)
            )
            .shadow(color: AppPalette.accent.opacity(configuration.isPressed ? 0 : 0.16), radius: 3, x: 0, y: 1)
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(isEnabled ? 1 : 0.42)
    }
}

struct AppSecondaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .medium))
            .foregroundStyle(AppPalette.textPrimary)
            .padding(.horizontal, 13)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(configuration.isPressed ? AppPalette.panelMuted : AppPalette.panelRaised)
                    .overlay(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .stroke(configuration.isPressed ? AppPalette.strongStroke : AppPalette.stroke, lineWidth: 1)
                    )
            )
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(isEnabled ? 1 : 0.42)
    }
}

struct AppDestructiveButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .medium))
            .foregroundStyle(AppPalette.destructive)
            .padding(.horizontal, 13)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(configuration.isPressed ? AppPalette.destructiveMuted.opacity(0.70) : AppPalette.destructiveMuted)
                    .overlay(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .stroke(AppPalette.destructive.opacity(0.25), lineWidth: 1)
                    )
            )
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(isEnabled ? 1 : 0.42)
    }
}

struct AppToolbarIconButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    var isDestructive = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(isDestructive ? AppPalette.destructive : AppPalette.textSecondary)
            .frame(width: 34, height: 34)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(isDestructive ? AppPalette.destructiveMuted : (configuration.isPressed ? AppPalette.panelMuted : AppPalette.panelRaised))
                    .overlay(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .stroke(isDestructive ? AppPalette.destructive.opacity(0.22) : AppPalette.stroke, lineWidth: 1)
                    )
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .opacity(isEnabled ? 1 : 0.38)
    }
}

struct AppFieldModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .textFieldStyle(.plain)
            .font(.system(size: 13, weight: .regular))
            .padding(.horizontal, 11)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(AppPalette.panel)
                    .overlay(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .stroke(AppPalette.strongStroke.opacity(0.66), lineWidth: 1)
                    )
            )
            .foregroundStyle(AppPalette.textPrimary)
    }
}

extension TextField {
    func appField() -> some View {
        modifier(AppFieldModifier())
    }
}

struct AppGroupBoxStyle: GroupBoxStyle {
    func makeBody(configuration: Configuration) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 9) {
                RoundedRectangle(cornerRadius: 2, style: .continuous)
                    .fill(AppPalette.accent)
                    .frame(width: 3, height: 17)
                configuration.label
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(AppPalette.panelMuted.opacity(0.55))

            Divider()
                .overlay(AppPalette.stroke)

            configuration.content
                .padding(14)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(AppPalette.panel)
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(AppPalette.stroke, lineWidth: 1)
                )
        )
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .shadow(color: AppPalette.shadow, radius: 3, x: 0, y: 1)
    }
}
