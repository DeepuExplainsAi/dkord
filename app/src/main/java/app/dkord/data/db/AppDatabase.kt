package app.dkord.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [
        TrackEntity::class, PlaylistEntity::class, PlaylistItemEntity::class,
        LikedEntity::class, HistoryEntity::class, DownloadEntity::class,
    ],
    version = 2,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun tracks(): TrackDao
    abstract fun playlists(): PlaylistDao
    abstract fun library(): LibraryDao
    abstract fun downloads(): DownloadDao

    companion object {
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE downloads ADD COLUMN location TEXT NOT NULL DEFAULT 'LEGACY'")
                db.execSQL("ALTER TABLE downloads ADD COLUMN deviceUri TEXT")
                db.execSQL("ALTER TABLE downloads ADD COLUMN deviceTree TEXT")
            }
        }
        fun build(context: Context) = Room.databaseBuilder(context, AppDatabase::class.java, "dkord.db")
            .addMigrations(MIGRATION_1_2).build()
    }
}
